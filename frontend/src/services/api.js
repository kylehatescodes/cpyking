import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export async function fetchInventory() {
  const { data } = await api.get('/inventory/');
  return data;
}

export async function createOrder(orderPayload) {
  const { data } = await api.post('/orders/', orderPayload);
  return data;
}

export default api;
