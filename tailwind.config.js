/** Rebuild static/css/tailwind.css with:
 *  tailwindcss -c tailwind.config.js -i tailwind.input.css -o static/css/tailwind.css --minify
 */
module.exports = {
  darkMode: "class",
  content: ["./templates/**/*.html"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
