# ---- Stage 1: Builder ----
FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir .

# Pre-install DuckDB extensions so they're baked into the image
ENV DUCKDB_EXTENSION_DIRECTORY=/opt/duckdb_extensions
RUN python -c "\
import duckdb, os; \
os.makedirs(os.environ['DUCKDB_EXTENSION_DIRECTORY'], exist_ok=True); \
con = duckdb.connect(); \
con.execute('INSTALL iceberg'); \
con.execute('INSTALL httpfs'); \
con.close(); \
print('DuckDB extensions installed')"

# ---- Stage 2: Runtime ----
FROM python:3.12-slim

RUN groupadd -r supsim && useradd -r -g supsim -d /home/supsim -m supsim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy pre-installed DuckDB extensions
COPY --from=builder /opt/duckdb_extensions /opt/duckdb_extensions
ENV DUCKDB_EXTENSION_DIRECTORY=/opt/duckdb_extensions

RUN chown -R supsim:supsim /app /opt/duckdb_extensions
USER supsim

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

CMD ["uvicorn", "supsim.main:app", "--host", "0.0.0.0", "--port", "8000"]
