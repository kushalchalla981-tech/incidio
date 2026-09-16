/** @type {import('next').NextConfig} */
const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
    ];
  },
  async redirects() {
    return [
      { source: "/dashboard", destination: "/incidents/dashboard", permanent: true },
      { source: "/logs", destination: "/incidents/logs", permanent: true },
      { source: "/analytics", destination: "/incidents/analytics", permanent: true },
      { source: "/scans", destination: "/security", permanent: true },
      { source: "/scans/:path*", destination: "/security/:path*", permanent: true },
      { source: "/settings", destination: "/incidents/settings", permanent: true },
    ];
  },
};

export default nextConfig;