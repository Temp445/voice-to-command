/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",      // Static export for Tauri
  trailingSlash: true,
  images: { unoptimized: true },
  experimental: {
    optimizePackageImports: ['lucide-react'],
  },
};

export default nextConfig;
