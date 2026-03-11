import { apiFetch } from './client';

export async function getHealth() {
  return apiFetch('/health');
}

export async function getReadiness() {
  return apiFetch('/ready');
}

export async function getRootInfo() {
  return apiFetch('/');
}
