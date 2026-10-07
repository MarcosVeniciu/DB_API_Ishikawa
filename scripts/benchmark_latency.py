"""
Script operacional para aferição do baseline de latência da DB_API_Ishikawa (Critério S5).
Mede p50, p95 e p99 por operação em rede interna.
Ref: Obsidian SDD [[sdd-db-api-seed-hardening]]
"""

import argparse
import json
import statistics
import time
from typing import Dict, List
import httpx


def calculate_metrics(latencies: List[float]) -> Dict[str, float]:
    """Calcula estatísticas de latência em milissegundos."""
    if not latencies:
        return {}
    sorted_lat = sorted(latencies)
    n = len(sorted_lat)
    p50_idx = int(n * 0.50)
    p95_idx = min(int(n * 0.95), n - 1)
    p99_idx = min(int(n * 0.99), n - 1)

    return {
        "count": n,
        "min_ms": round(sorted_lat[0], 2),
        "mean_ms": round(statistics.mean(sorted_lat), 2),
        "p50_ms": round(sorted_lat[p50_idx], 2),
        "p95_ms": round(sorted_lat[p95_idx], 2),
        "p99_ms": round(sorted_lat[p99_idx], 2),
        "max_ms": round(sorted_lat[-1], 2),
    }


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

        for i in range(iterations):
            # 1. Healthcheck Ready
            t0 = time.perf_counter()
            r_health = client.get("/health/ready")
            t_health = (time.perf_counter() - t0) * 1000
            if r_health.status_code == 200:
                results["health_ready"].append(t_health)

            # 2. List Producers
            t0 = time.perf_counter()
            r_prod = client.get("/v1/producers?limit=10", headers=headers)
            t_prod = (time.perf_counter() - t0) * 1000
            if r_prod.status_code == 200:
                results["list_producers"].append(t_prod)

            # 3. Auth Verify
            t0 = time.perf_counter()
            r_auth = client.post(
                "/v1/auth/verify",
                json={
                    "email": "consultor@educampo.com",
                    "password": "admin123",
                    "role": "consultant",
                },
                headers=headers,
            )
            t_auth = (time.perf_counter() - t0) * 1000
            if r_auth.status_code == 200:
                results["auth_verify"].append(t_auth)

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
        status_str = "APROVADO (p95 < 50ms)" if p95 < 50.0 else "REPROVADO (p95 >= 50ms)"
        print(f"Endpoint '{endpoint}': p95={p95} ms -> {status_str}")
        if p95 >= 50.0:
            all_passed = False

    if all_passed:
        print("\n=> CRITÉRIO S5 ATINGIDO COM SUCESSO: Latência p95 < 50 ms em todas as operações.")
    else:
        print("\n=> ALERTA: Algumas operações excederam a meta de 50 ms.")


if __name__ == "__main__":
    main()
