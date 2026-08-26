/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        pastel: {
          bg: "#F8F7FF",
          secondary: "#FDFDFF",
          card: "#FFFFFF",
          lavender: "#CDB4DB",
          blue: "#A2D2FF",
          mint: "#BDE0BE",
          peach: "#FFD6A5",
          pink: "#FFC8DD",
          text: "#3D405B",
          textSecondary: "#6B7280",
          success: "#95D5B2",
          warning: "#FFD6A5",
          error: "#FFB4A2"
        }
      },
      boxShadow: {
        soft: "0 4px 20px rgba(0,0,0,0.06)",
        "soft-hover": "0 8px 30px rgba(0,0,0,0.10)"
      },
      borderRadius: {
        'xl': '20px',
      }
    },
  },
  plugins: [],
}
