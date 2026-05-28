/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",      // Static export for Tauri
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
