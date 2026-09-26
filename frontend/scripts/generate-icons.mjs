import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = path.join(root, "public/icon.svg");
await Promise.all([
  [192, "icon-192.png"], [512, "icon-512.png"], [512, "icon-maskable-512.png"], [180, "apple-touch-icon.png"],
].map(([size, name]) => sharp(source).resize(size, size).png().toFile(path.join(root, "public", name))));
console.log("Generated four original Open Tennis PWA icons.");
