import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import Alert from '../components/Alert';
import logoUrl from '../../../faculty-frontend/logo.png'

const DevLogin = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { login } = useAuth();

  // Pre-registered student emails for quick selection
  const studentEmails = [
    { email: 'student1@example.com', name: 'Student 1' },
    { email: 'student2@example.com', name: 'Student 2' },
    { email: 'student3@example.com', name: 'Student 3' },
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Dev endpoint is at /api/dev/ not /api/v1/
      const apiBase = api?.defaults?.baseURL || ''
      const origin = apiBase.replace(/\/api\/v1\/?$/, '')
      const response = await fetch(`${origin}/api/dev/sso-login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      
      if (!response.ok) {
        if (response.status === 404) {
          throw { response: { status: 404 } };
        }
        throw new Error('Login failed');
      }
      
      const data = await response.json();
      
      // Role is inside user object from API response
      if (data.user.role !== 'student') {
        setError('This email belongs to a faculty member. Please use the Faculty Panel.');
        setLoading(false);
        return;
      }

      await login(data);
      navigate('/dashboard');
    } catch (err) {
      console.error('Login error:', err);
      if (err.response?.status === 404) {
        setError('User not found. Please use a pre-registered email.');
      } else {
        setError(err.response?.data?.error || 'Login failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = (studentEmail) => {
    setEmail(studentEmail);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
        <img src={logoUrl} alt="PBL Scheduler" className="h-14 w-14 object-contain mx-auto mb-4" />
        <h1 className="text-2xl font-bold text-center mb-2">Student Portal</h1>
        <p className="text-gray-500 text-center mb-6">Development Login</p>
        
        {error && <Alert variant="error" onClose={() => setError('')}>{error}</Alert>}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email Address
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="student1@example.com"
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading || !email}
            className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div className="mt-6">
          <p className="text-sm text-gray-500 text-center mb-3">Quick Login (Test Accounts)</p>
          <div className="space-y-2">
            {studentEmails.map((student) => (
              <button
                key={student.email}
                onClick={() => handleQuickLogin(student.email)}
                className="w-full text-left px-3 py-2 text-sm bg-gray-50 hover:bg-gray-100 rounded border border-gray-200"
              >
                <span className="font-medium">{student.name}</span>
                <span className="text-gray-500 text-xs ml-2">({student.email})</span>
              </button>
            ))}
          </div>
        </div>

        <p className="mt-6 text-xs text-gray-400 text-center">
          DEV MODE ONLY - Teacher assignments are loaded from database
        </p>
      </div>
    </div>
  );
};

export default DevLogin;
