/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone", // small self-contained server build for the Docker image
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
