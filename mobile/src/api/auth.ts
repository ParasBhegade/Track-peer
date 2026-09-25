import { apiClient, setAuthToken } from './client';

export const login = async (email: string, password: string) => {
  const params = new URLSearchParams();
  params.append('username', email); // FastAPI OAuth2PasswordRequestForm uses 'username'
  params.append('password', password);

  const response = await apiClient.post('/api/v1/auth/login', params, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  
  if (response.data.access_token) {
    setAuthToken(response.data.access_token);
  }
  
  return response.data;
};
