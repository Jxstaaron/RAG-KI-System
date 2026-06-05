import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Erlaubt den Zugriff auf den Next.js-Dev-Server über lokale Netzwerk-IPs.
  allowedDevOrigins: ["10.11.117.110", "192.168.178.33"],
};

export default nextConfig;
