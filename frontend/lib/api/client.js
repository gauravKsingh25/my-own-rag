const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class APIError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.body = body;
  }
}

export class RateLimitError extends APIError {
  constructor(message, retryAfter, body) {
    super(message, 429, body);
    this.name = 'RateLimitError';
    this.retryAfter = retryAfter ?? 60;
  }
}

export class QuotaError extends APIError {
  constructor(message, resetTime, body) {
    super(message, 429, body);
    this.name = 'QuotaError';
    this.resetTime = resetTime;
  }
}

export class ServiceUnavailableError extends APIError {
  constructor(message, body) {
    super(message, 503, body);
    this.name = 'ServiceUnavailableError';
  }
}

export class NetworkError extends APIError {
  constructor() {
    super('Network error — is the backend running?', 0, {});
    this.name = 'NetworkError';
  }
}

export async function apiFetch(path, options = {}) {
  const url = `${BASE_URL}${path}`;

  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new NetworkError();
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message = body.error || (Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail) || 'Request failed';

    if (response.status === 429) {
      const errorType = body.error_type || '';
      if (errorType === 'quota_exceeded' || body.reset_time) {
        throw new QuotaError(message, body.reset_time, body);
      }
      throw new RateLimitError(message, body.retry_after, body);
    }

    if (response.status === 503) {
      throw new ServiceUnavailableError(message, body);
    }

    throw new APIError(message, response.status, body);
  }

  return response.json();
}
