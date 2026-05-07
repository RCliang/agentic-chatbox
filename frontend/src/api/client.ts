import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export async function resumeInterruptAPI(conversationId: string, action: string, payload: Record<string, unknown> = {}) {
  return api.post('/api/chat/resume', {
    conversation_id: conversationId,
    action,
    payload,
  });
}

export async function getConversationStatus(conversationId: string) {
  return api.get(`/api/chat/conversations/${conversationId}/status`);
}

export default api;
