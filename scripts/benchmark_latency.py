"""
Script operacional para aferição do baseline de latência da DB_API_Ishikawa (Critério S5).
Mede p50, p95 e p99 por operação em rede interna.
Ref: Obsidian SDD [[sdd-db-api-seed-hardening]]
"""

import argparse
import json
import statistics
import time
from typing import Any, Dict, List, Optional
import httpx

P50_RATIO: float = 0.50
P95_RATIO: float = 0.95
P99_RATIO: float = 0.99
S5_TARGET_P95_MS: float = 50.0


def calculate_metrics(latencies: List[float]) -> Dict[str, float]:
    """Calcula estatísticas de latência em milissegundos."""
    if not latencies:
        return {}
    sorted_lat = sorted(latencies)
    n = len(sorted_lat)
    p50_idx = int(n * P50_RATIO)
    p95_idx = min(int(n * P95_RATIO), n - 1)
    p99_idx = min(int(n * P99_RATIO), n - 1)

    return {
        "count": n,
        "min_ms": round(sorted_lat[0], 2),
        "mean_ms": round(statistics.mean(sorted_lat), 2),
        "p50_ms": round(sorted_lat[p50_idx], 2),
        "p95_ms": round(sorted_lat[p95_idx], 2),
        "p99_ms": round(sorted_lat[p99_idx], 2),
        "max_ms": round(sorted_lat[-1], 2),
    }


def _measure_endpoint_latency(
    client: httpx.Client,
    method: str,
    path: str,
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> Optional[float]:
    """Mede a latência de uma chamada HTTP em ms se a resposta for bem-sucedida (200 OK)."""
    t0 = time.perf_counter()
    response = client.request(method, path, headers=headers, json=json_body)
    duration_ms = (time.perf_counter() - t0) * 1000
    if response.status_code == 200:
        return duration_ms
    return None


def run_benchmark(
    base_url: str,
    token: str,
    iterations: int = 100,
) -> Dict[str, Dict[str, float]]:
    """Executa requisições HTTP e coleta métricas de tempo de resposta."""
    headers = {"X-Service-Token": token}
    results: Dict[str, List[float]] = {
        "health_ready": [],
        "list_producers": [],
        "auth_verify": [],
    }

    with httpx.Client(base_url=base_url, timeout=5.0) as client:
        print(f"Iniciando benchmark contra {base_url} ({iterations} iterações)...")

        for _ in range(iterations):
            # 1. Healthcheck Ready
            lat_health = _measure_endpoint_latency(client, "GET", "/health/ready")
            if lat_health is not None:
                results["health_ready"].append(lat_health)

            # 2. List Producers
            lat_prod = _measure_endpoint_latency(
                client, "GET", "/v1/producers?limit=10", headers=headers
            )
            if lat_prod is not None:
                results["list_producers"].append(lat_prod)

            # 3. Auth Verify
            lat_auth = _measure_endpoint_latency(
                client,
                "POST",
                "/v1/auth/verify",
                headers=headers,
                json_body={
                    "email": "consultor@educampo.com",
                    "password": "admin123",
                    "role": "consultant",
                },
            )
            if lat_auth is not None:
                results["auth_verify"].append(lat_auth)

    report = {name: calculate_metrics(lats) for name, lats in results.items()}
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark de latência DB_API_Ishikawa (Meta p95 < 50ms)"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8002",
        help="URL base da API (ex: http://localhost:8002)",
    )
    parser.add_argument(
        "--token",
        type=str,
        default="local-dev-service-token-change-in-production",
        help="X-Service-Token da aplicação",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=50,
        help="Número de requisições por endpoint",
    )
    args = parser.parse_args()

    report = run_benchmark(
        base_url=args.base_url,
        token=args.token,
        iterations=args.iterations,
    )

    print("\n================= RELATÓRIO DE BASELINE (p95) =================")
    print(json.dumps(report, indent=2))
    print("================================================================")

    all_passed = True
    for endpoint, metrics in report.items():
        p95 = metrics.get("p95_ms", 999.0)
        status_str = (
            f"APROVADO (p95 < {S5_TARGET_P95_MS}ms)"
            if p95 < S5_TARGET_P95_MS
            else f"REPROVADO (p95 >= {S5_TARGET_P95_MS}ms)"
        )
        print(f"Endpoint '{endpoint}': p95={p95} ms -> {status_str}")
        if p95 >= S5_TARGET_P95_MS:
            all_passed = False

    if all_passed:
        print(
            f"\n=> CRITÉRIO S5 ATINGIDO COM SUCESSO: Latência p95 < {S5_TARGET_P95_MS} ms em todas as operações."
        )
    else:
        print("\n=> ALERTA: Algumas operações excederam a meta de 50 ms.")


if __name__ == "__main__":
    main()
