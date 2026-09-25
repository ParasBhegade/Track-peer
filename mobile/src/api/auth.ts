import { apiClient, setAuthToken } from './client';

export const login = async (email: string, password: string) => {
  const response = await apiClient.post('/api/v1/auth/login', {
    email,
    password
  });

  
  if (response.data.tokens && response.data.tokens.access_token) {
    setAuthToken(response.data.tokens.access_token);
  }
  
  return response.data;
};
