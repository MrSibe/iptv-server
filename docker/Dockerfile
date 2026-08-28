From python:3.12-slim AS builder

WORKDIR /app
COPY . .

ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

From python:3.12-slim AS runtime

COPY --from=builder /wheels /wheels
COPY --from=builder /app /app

RUN pip install --no-cache-dir --no-index --find-links /wheels -r /app/requirements.txt

WORKDIR /app

EXPOSE 8889

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8889"]