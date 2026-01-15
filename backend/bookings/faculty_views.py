"""Faculty-only endpoints for booking status and absence/rebooking workflow.

These endpoints exist alongside the router-based /api/v1/bookings/faculty/* API.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework import status, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsFaculty
from core.subjects import is_allowed_subject, normalize_subject
from core.models import User

from .models import Booking, RebookingPermission
from .serializers import BookingSerializer


class MarkBookingStatusSerializer(serializers.Serializer):
    # Optional field: some UIs may send a reason in future
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class AllowRebookingSerializer(serializers.Serializer):
    student_id = serializers.UUIDField(required=True)
    subject = serializers.CharField(required=True)

    def validate_subject(self, value):
        value = (value or '').strip()
        if not is_allowed_subject(value):
            raise serializers.ValidationError({'detail': 'Invalid subject'})
        return value


class FacultyMarkAbsentView(APIView):
    permission_classes = [IsAuthenticated, IsFaculty]

    @transaction.atomic
    def patch(self, request, booking_id):
        try:
            booking = Booking.objects.select_related('slot', 'slot__faculty', 'student').get(pk=booking_id)
        except Booking.DoesNotExist:
            return Response({'detail': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

        if booking.slot.faculty_id != request.user.id:
            return Response({'detail': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

        # Idempotent
        if booking.status == Booking.Status.ABSENT:
            if booking.absent_at is None:
                booking.absent_at = booking.updated_at or timezone.now()
                booking.save(update_fields=['absent_at', 'updated_at'])
            return Response(BookingSerializer(booking).data, status=status.HTTP_200_OK)

        if booking.status != Booking.Status.CONFIRMED:
            return Response({'detail': 'Only confirmed bookings can be marked absent'}, status=status.HTTP_400_BAD_REQUEST)

        booking.status = Booking.Status.ABSENT
        booking.absent_at = timezone.now()
        booking.save(update_fields=['status', 'absent_at', 'updated_at'])
        return Response(BookingSerializer(booking).data, status=status.HTTP_200_OK)


class FacultyMarkCompletedView(APIView):
    permission_classes = [IsAuthenticated, IsFaculty]

    @transaction.atomic
    def patch(self, request, booking_id):
        try:
            booking = Booking.objects.select_related('slot', 'slot__faculty', 'student').get(pk=booking_id)
        except Booking.DoesNotExist:
            return Response({'detail': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

        if booking.slot.faculty_id != request.user.id:
            return Response({'detail': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

        # Idempotent
        if booking.status == Booking.Status.COMPLETED:
            return Response(BookingSerializer(booking).data, status=status.HTTP_200_OK)

        if booking.status != Booking.Status.CONFIRMED:
            return Response({'detail': 'Only confirmed bookings can be marked completed'}, status=status.HTTP_400_BAD_REQUEST)

        booking.status = Booking.Status.COMPLETED
        booking.save(update_fields=['status', 'updated_at'])
        return Response(BookingSerializer(booking).data, status=status.HTTP_200_OK)


class FacultyCancelBookingView(APIView):
    permission_classes = [IsAuthenticated, IsFaculty]

    @transaction.atomic
    def patch(self, request, booking_id):
        serializer = MarkBookingStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            booking = Booking.objects.select_related('slot', 'slot__faculty', 'student').get(pk=booking_id)
        except Booking.DoesNotExist:
            return Response({'detail': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

        if booking.slot.faculty_id != request.user.id:
            return Response({'detail': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

        if booking.status == Booking.Status.CANCELLED:
            return Response(BookingSerializer(booking).data, status=status.HTTP_200_OK)

        if booking.status != Booking.Status.CONFIRMED:
            return Response({'detail': 'Only confirmed bookings can be cancelled'}, status=status.HTTP_400_BAD_REQUEST)

        reason = serializer.validated_data.get('reason', '')
        booking.cancel(reason=reason, force=True)
        return Response(BookingSerializer(booking).data, status=status.HTTP_200_OK)


class FacultyAbsentStudentsView(APIView):
    permission_classes = [IsAuthenticated, IsFaculty]

    def get(self, request):
        # Only absences on THIS faculty's slots
        qs = (
            Booking.objects
            .filter(slot__faculty=request.user, status=Booking.Status.ABSENT)
            .select_related('student', 'slot')
            .order_by('-absent_at', '-updated_at')
        )

        # Deduplicate by (student, subject) and keep latest
        latest = {}
        for booking in qs:
            subject = normalize_subject(booking.slot.subject)
            key = (booking.student_id, subject)
            if key not in latest:
                latest[key] = booking

        results = []
        for booking in latest.values():
            subject = normalize_subject(booking.slot.subject)
            absent_time = booking.absent_at or booking.updated_at

            permission = RebookingPermission.objects.filter(
                student=booking.student,
                subject=subject,
                teacher_external_id=request.user.pbl_user_id,
            ).only('updated_at').first()

            resolved = permission is not None and (absent_time and permission.updated_at >= absent_time)
            if resolved:
                # Keep the list focused on unresolved absences.
                continue

            results.append({
                'student': {
                    'id': str(booking.student.id),
                    'name': booking.student.name,
                    'email': booking.student.email,
                },
                'subject': subject,
                'booking_id': str(booking.id),
                'status': booking.status,
                'marked_absent_at': absent_time.isoformat() if absent_time else None,
                'slot': {
                    'id': str(booking.slot.id),
                    'start_time': booking.slot.start_time.isoformat() if booking.slot.start_time else None,
                    'end_time': booking.slot.end_time.isoformat() if booking.slot.end_time else None,
                },
            })

        return Response(results, status=status.HTTP_200_OK)


class FacultyAllowRebookingForBookingView(APIView):
    permission_classes = [IsAuthenticated, IsFaculty]

    @transaction.atomic
    def post(self, request, booking_id):
        try:
            booking = Booking.objects.select_related('slot', 'slot__faculty', 'student').get(pk=booking_id)
        except Booking.DoesNotExist:
            return Response({'detail': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

        if booking.slot.faculty_id != request.user.id:
            return Response({'detail': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

        if booking.status != Booking.Status.ABSENT:
            return Response({'detail': 'Only absent bookings can be approved for rebooking'}, status=status.HTTP_400_BAD_REQUEST)

        faculty = request.user
        if not faculty.pbl_user_id:
            return Response({'detail': 'Faculty PBL ID not configured'}, status=status.HTTP_400_BAD_REQUEST)

        subject = normalize_subject(booking.slot.subject)
        student = booking.student

        permission, _ = RebookingPermission.objects.update_or_create(
            student=student,
            subject=subject,
            defaults={'teacher_external_id': faculty.pbl_user_id},
        )

        return Response({
            'detail': 'Rebooking allowed',
            'id': str(permission.id),
            'student_id': str(permission.student_id),
            'subject': permission.subject,
            'teacher_external_id': permission.teacher_external_id,
            'updated_at': permission.updated_at,
        }, status=status.HTTP_201_CREATED)


class FacultyAllowRebookingView(APIView):
    permission_classes = [IsAuthenticated, IsFaculty]

    @transaction.atomic
    def post(self, request):
        serializer = AllowRebookingSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            message = errors.get('detail') if isinstance(errors, dict) else None
            if message is None and isinstance(errors, dict):
                first_key = next(iter(errors.keys()), None)
                if first_key is not None:
                    message = errors.get(first_key)
            message = message[0] if isinstance(message, list) and message else message
            return Response({'detail': message or 'Invalid request'}, status=status.HTTP_400_BAD_REQUEST)

        faculty = request.user
        if not faculty.pbl_user_id:
            return Response({'detail': 'Faculty PBL ID not configured'}, status=status.HTTP_400_BAD_REQUEST)

        subject = serializer.validated_data['subject']
        student_id = serializer.validated_data['student_id']

        try:
            student = User.objects.get(pk=student_id, role='student')
        except User.DoesNotExist:
            return Response({'detail': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)

        # Only allow rebooking if the student has been marked absent for this subject
        has_absent = Booking.objects.filter(
            student=student,
            status=Booking.Status.ABSENT,
            slot__subject=subject,
            slot__faculty__pbl_user_id=faculty.pbl_user_id,
        ).exists()

        if not has_absent:
            return Response({'detail': 'Student is not marked absent for this subject'}, status=status.HTTP_400_BAD_REQUEST)

        permission, _ = RebookingPermission.objects.update_or_create(
            student=student,
            subject=subject,
            defaults={'teacher_external_id': faculty.pbl_user_id},
        )

        return Response({
            'id': str(permission.id),
            'student_id': str(permission.student_id),
            'subject': permission.subject,
            'teacher_external_id': permission.teacher_external_id,
            'created_at': permission.created_at,
        }, status=status.HTTP_201_CREATED)
