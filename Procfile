web: uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port ${PORT:-8000}
assets: npx esbuild frontend/main.ts --bundle --outfile=static/app.js --watch --sourcemap
