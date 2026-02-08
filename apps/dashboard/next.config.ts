import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  webpack: (config) => {
    // Resolve @sam/api-contracts alias
    config.resolve.alias["@sam/api-contracts"] = path.resolve(
      __dirname,
      "../../libs/api-contracts/typescript/schemas.ts"
    );
    // Ensure external libs resolve zod from dashboard's node_modules
    config.resolve.modules = [
      path.resolve(__dirname, "node_modules"),
      "node_modules",
      ...(config.resolve.modules || []),
    ];
    return config;
  },
};

export default nextConfig;
