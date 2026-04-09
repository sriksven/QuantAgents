"""
Qiskit availability validator — run standalone to check quantum dependencies.
Python: python backend/scripts/validate_quantum.py
"""
from __future__ import annotations

import sys


def run_validation():
    results = []

    # 1. Qiskit core
    try:
        import qiskit
        results.append(("qiskit", "✅", qiskit.__version__))
    except ImportError:
        results.append(("qiskit", "❌ not installed", "pip install qiskit"))

    # 2. Qiskit Aer simulator
    try:
        import qiskit_aer
        results.append(("qiskit-aer", "✅", qiskit_aer.__version__))
    except ImportError:
        results.append(("qiskit-aer", "❌ not installed", "pip install qiskit-aer"))

    # 3. Qiskit Algorithms (for QAOA)
    try:
        import qiskit_algorithms
        results.append(("qiskit-algorithms", "✅", qiskit_algorithms.__version__))
    except ImportError:
        results.append(("qiskit-algorithms", "⚠️ optional", "pip install qiskit-algorithms"))

    # 4. NumPy
    try:
        import numpy as np
        results.append(("numpy", "✅", np.__version__))
    except ImportError:
        results.append(("numpy", "❌", "required"))

    # 5. SciPy
    try:
        import scipy
        results.append(("scipy", "✅", scipy.__version__))
    except ImportError:
        results.append(("scipy", "❌", "required for VaR"))

    # 6. Test QAOA circuit construction
    qaoa_status = "❌ skipped (qiskit unavailable)"
    try:
        from qiskit import QuantumCircuit
        from qiskit_aer import AerSimulator
        qc = QuantumCircuit(2)
        qc.h([0, 1])
        qc.cx(0, 1)
        qc.measure_all()
        backend = AerSimulator()
        from qiskit import transpile
        t = transpile(qc, backend)
        job = backend.run(t, shots=100)
        counts = job.result().get_counts()
        qaoa_status = f"✅ circuit test passed (counts: {dict(list(counts.items())[:2])})"
    except Exception as exc:
        qaoa_status = f"❌ circuit test failed: {exc}"

    # 7. Test quantum-inspired fallback (always available)
    qi_status = "❌"
    try:
        sys.path.insert(0, ".")
        from mcp_servers.quantum_finance import _quantum_inspired_optimize
        import numpy as np
        mu = np.array([0.10, 0.12, 0.08])
        cov = np.eye(3) * 0.04
        weights, backend = _quantum_inspired_optimize(mu, cov, 1.0, 3, None)
        assert abs(sum(weights) - 1.0) < 0.001
        qi_status = f"✅ SA fallback OK — weights sum to {sum(weights):.3f}"
    except Exception as exc:
        qi_status = f"❌ fallback failed: {exc}"

    # Print report
    print("\n" + "="*60)
    print("  QuantAgents — Quantum Module Validation")
    print("="*60)
    for name, status, detail in results:
        print(f"  {status}  {name:25s}  {detail}")
    print()
    print(f"  QAOA Circuit Test:  {qaoa_status}")
    print(f"  Quantum-Inspired:   {qi_status}")
    print("="*60)

    all_critical_ok = all(s == "✅" for _, s, _ in results if "optional" not in s)
    if all_critical_ok:
        print("\n  ✅ All critical dependencies satisfied.\n")
        return 0
    else:
        print("\n  ⚠️  Some dependencies missing — install with:")
        print("  pip install qiskit qiskit-aer scipy numpy\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_validation())
