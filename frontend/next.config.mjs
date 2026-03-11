/** @type {import('next').NextConfig} */
const nextConfig = {
  /**
   * API proxy rewrites — forwards /api/v1/* and /health, /ready
   * to the FastAPI backend so there are no CORS issues in production.
   * The NEXT_PUBLIC_API_URL env var is still used in the browser
   * for direct fetches during development.
   */
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
    return [
      { source: '/api/v1/:path*', destination: `${backendUrl}/api/v1/:path*` },
      { source: '/health',        destination: `${backendUrl}/health` },
      { source: '/ready',         destination: `${backendUrl}/ready` },
    ];
  },
};

export default nextConfig;

