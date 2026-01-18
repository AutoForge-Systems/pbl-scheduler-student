"""
Booking Views
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Booking
from .serializers import (
    BookingSerializer,
    BookingCreateSerializer,
    BookingCancelSerializer
)
from core.permissions import IsFaculty, IsStudent
from core.subjects import normalize_subject


class StudentBookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for students to manage their bookings.
    
    Students can:
    - View their bookings
    - Create a new booking (one at a time)
    - Cancel their booking
    """
    permission_classes = [IsAuthenticated, IsStudent]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return BookingCreateSerializer
        if self.action == 'cancel':
            return BookingCancelSerializer
        return BookingSerializer
    
    def get_queryset(self):
        """Return only the student's bookings for slots in the future."""
        from django.utils import timezone
        return Booking.objects.filter(
            student=self.request.user,
            slot__start_time__gt=timezone.now()
        ).select_related('slot', 'slot__faculty', 'student')
    
    def list(self, request):
        """List student's bookings."""
        queryset = self.get_queryset()
        
        # Optional status filter
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def create(self, request):
        """Create a new booking."""
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            # Normalize DRF errors into {detail: "message"}
            errors = serializer.errors
            message = None
            if isinstance(errors, dict):
                # Prefer explicit detail
                if 'detail' in errors:
                    message = errors.get('detail')
                else:
                    first_key = next(iter(errors.keys()), None)
                    if first_key is not None:
                        message = errors.get(first_key)
            message = message[0] if isinstance(message, list) and message else message
            return Response({'detail': message or 'Invalid request'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            booking = serializer.save()
            return Response(
                BookingSerializer(booking).data,
                status=status.HTTP_201_CREATED
            )
        except DjangoValidationError as e:
            message = None
            if hasattr(e, 'messages') and e.messages:
                message = e.messages[0]
            elif hasattr(e, 'message'):
                message = e.message
            return Response(
                {'detail': message or str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a booking."""
        booking = self.get_object()
        
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request, 'booking': booking}
        )
        if not serializer.is_valid():
            errors = serializer.errors
            message = errors.get('detail') if isinstance(errors, dict) else None
            if message is None and isinstance(errors, dict):
                first_key = next(iter(errors.keys()), None)
                if first_key is not None:
                    message = errors.get(first_key)
            message = message[0] if isinstance(message, list) and message else message
            return Response({'detail': message or 'Invalid request'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            booking.cancel(reason=serializer.validated_data.get('reason', ''))
            return Response(BookingSerializer(booking).data)
        except DjangoValidationError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def update(self, request, *args, **kwargs):
        """Disable update - bookings cannot be modified."""
        return Response(
            {'detail': 'Bookings cannot be modified. Cancel and rebook instead.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def partial_update(self, request, *args, **kwargs):
        """Disable partial update."""
        return self.update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Disable delete - use cancel instead."""
        return Response(
            {'detail': 'Use the cancel endpoint to cancel a booking.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get the student's current active bookings.

        Business rule: one confirmed booking per subject (max 2 subjects).
        Returns a list (possibly empty).
        """
        bookings = self.get_queryset().filter(status='confirmed').order_by('slot__start_time')
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='blocked-subjects')
    def blocked_subjects(self, request):
        """Return subjects for which the student is blocked due to absence.

        A subject is blocked when:
        - student has at least one booking with status=absent for that subject
        - and no RebookingPermission exists for that student+subject for the same faculty
          (or the permission predates the absence).
        """
        from .models import RebookingPermission

        student = request.user

        # Consider all absences for this student; dedupe by subject and keep the most recent unresolved one.
        absences = (
            Booking.objects
            .filter(student=student, status=Booking.Status.ABSENT)
            .select_related('slot', 'slot__faculty')
            .order_by('-absent_at', '-updated_at')
        )

        blocked_by_subject = {}
        for b in absences:
            subject = normalize_subject(b.slot.subject)
            teacher_external_id = getattr(b.slot.faculty, 'pbl_user_id', None)
            absent_time = b.absent_at or b.updated_at

            if not teacher_external_id:
                # If we cannot identify the faculty externally, treat as blocked for safety.
                unresolved = True
            else:
                permission = (
                    RebookingPermission.objects
                    .filter(student=student, subject=subject, teacher_external_id=teacher_external_id)
                    .only('updated_at')
                    .first()
                )
                unresolved = permission is None or (absent_time and permission.updated_at < absent_time)

            if not unresolved:
                continue

            if subject in blocked_by_subject:
                continue

            blocked_by_subject[subject] = {
                'subject': subject,
                'blocked': True,
                'detail': f'You were marked absent for {subject}. Please contact your faculty to book another slot.',
                'absent_at': absent_time.isoformat() if absent_time else None,
                'booking_id': str(b.id),
            }

        return Response({'blocked_subjects': list(blocked_by_subject.values())})


class FacultyBookingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for faculty to view bookings on their slots.
    
    Faculty can:
    - View all bookings on their slots
    """
    permission_classes = [IsAuthenticated, IsFaculty]
    serializer_class = BookingSerializer
    
    def get_queryset(self):
        """Return bookings on faculty's slots for slots in the future."""
        from django.utils import timezone
        return Booking.objects.filter(
            slot__faculty=self.request.user,
            slot__start_time__gt=timezone.now()
        ).select_related('slot', 'slot__faculty', 'student')
    
    def list(self, request):
        """List bookings on faculty's slots."""
        queryset = self.get_queryset()
        
        # Optional status filter
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Optional: filter by confirmed only
        if request.query_params.get('confirmed_only', 'false').lower() == 'true':
            queryset = queryset.filter(status='confirmed')
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a booking on the faculty's slot."""
        booking = self.get_object()
        # Faculty cancellation is not restricted by student cancellation window.
        reason = request.data.get('reason', '')
        if reason is None:
            reason = ''
        if not isinstance(reason, str):
            return Response({'detail': 'Invalid request'}, status=status.HTTP_400_BAD_REQUEST)
        if len(reason) > 500:
            return Response({'detail': 'Reason too long'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            booking.cancel(reason=reason, force=True)
            return Response(BookingSerializer(booking).data)
        except DjangoValidationError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        """Mark a confirmed booking as completed (evaluated)."""
        booking = self.get_object()

        if booking.status != Booking.Status.CONFIRMED:
            return Response(
                {'detail': 'Only confirmed bookings can be marked as completed'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking.status = Booking.Status.COMPLETED
        booking.save(update_fields=['status', 'updated_at'])
        return Response(BookingSerializer(booking).data)
