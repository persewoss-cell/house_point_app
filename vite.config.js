import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GitHub Pages 주소(https://아이디.github.io/house_point_app/)에 맞춘 경로
export default defineConfig({
  base: "./",
  plugins: [react()],
});
