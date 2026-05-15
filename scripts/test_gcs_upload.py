#!/usr/bin/env python3
"""Smoke test del upload de results a GCS.

Uso (desde la raíz del repo spark):
    SPARK_RESULTS_BUCKET=nelson-studies python3 scripts/test_gcs_upload.py

Verifica el ciclo completo:
  1. Crea un directorio temporal con un JSON dummy (imitando lo que el
     agente de Spark deja en workspace/results/{task_id}/).
  2. Llama _upload_task_results_to_gcs() para subirlo.
  3. Lista los blobs en GCS para confirmar que existen y los descarga.
  4. Limpia (borra los blobs subidos + el dir temporal).

No requiere PowerFactory ni una corrida real del agente — solo la
configuración GCS de la VM (ADC vía `gcloud auth application-default login`).
"""

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

# Permite importar server.py desde la raíz del repo
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

import config  # noqa: E402

config.load_dotenv()


def main() -> int:
    bucket_name = config.get("SPARK_RESULTS_BUCKET", "")
    if not bucket_name:
        print("ERROR: SPARK_RESULTS_BUCKET no está seteado (ni en env ni en .env)")
        print("Probá: SPARK_RESULTS_BUCKET=nelson-studies python3 scripts/test_gcs_upload.py")
        return 2

    print(f"Bucket: gs://{bucket_name}")
    prefix = config.get("SPARK_RESULTS_GCS_PREFIX", "spark-results").strip("/")
    print(f"Prefix: {prefix}/")

    # Import diferido para que el error de import sea claro si falta la dep.
    try:
        from google.cloud import storage as _gcs_storage
    except ImportError:
        print("ERROR: google-cloud-storage no instalado. uv sync --extra server")
        return 2

    from server import _upload_task_results_to_gcs  # noqa: E402

    task_id = f"smoketest-{uuid.uuid4().hex[:6]}"
    print(f"Task id: {task_id}")

    with tempfile.TemporaryDirectory() as tmpdir:
        results_dir = Path(tmpdir) / task_id
        results_dir.mkdir(parents=True)

        # Dos archivos JSON + uno que arranca con _ (debe ser ignorado).
        payload_a = {"hello": "world", "ts": "2026-05-15"}
        payload_b = {"items": [1, 2, 3], "ok": True}
        (results_dir / "alpha.json").write_text(
            json.dumps(payload_a, indent=2), encoding="utf-8"
        )
        (results_dir / "beta.json").write_text(
            json.dumps(payload_b, indent=2), encoding="utf-8"
        )
        (results_dir / "_internal.json").write_text("{}", encoding="utf-8")

        print(f"\nFiles en {results_dir}:")
        for f in sorted(results_dir.iterdir()):
            print(f"  - {f.name} ({f.stat().st_size} B)")

        print("\nSubiendo a GCS...")
        artifacts = _upload_task_results_to_gcs(task_id, results_dir)

        if not artifacts:
            print("ERROR: _upload_task_results_to_gcs devolvió lista vacía.")
            print("Revisar que ADC esté configurado: gcloud auth application-default login")
            return 1

        print(f"Subidos {len(artifacts)} artifacts:")
        for a in artifacts:
            print(f"  - {a['name']:12s}  {a['gcs_uri']}  ({a['size_bytes']} B)")

        # _internal.json no debe haber subido
        names = [a["name"] for a in artifacts]
        if "_internal" in names:
            print("ERROR: archivo _internal.json fue subido (debería ignorarse).")
            return 1

        # Verificación read-back
        print("\nDescargando para verificar contenido...")
        client = _gcs_storage.Client()
        bucket = client.bucket(bucket_name)
        ok = True
        for a in artifacts:
            blob_path = a["gcs_uri"].replace(f"gs://{bucket_name}/", "")
            blob = bucket.blob(blob_path)
            if not blob.exists():
                print(f"  ✗ {a['name']}: blob no existe en GCS")
                ok = False
                continue
            content = blob.download_as_bytes().decode("utf-8")
            try:
                json.loads(content)
                print(f"  ✓ {a['name']}: descargado y parseable")
            except json.JSONDecodeError as e:
                print(f"  ✗ {a['name']}: contenido no es JSON válido — {e}")
                ok = False

        # Limpieza
        print("\nLimpiando blobs subidos...")
        for a in artifacts:
            blob_path = a["gcs_uri"].replace(f"gs://{bucket_name}/", "")
            try:
                bucket.blob(blob_path).delete()
                print(f"  - borrado {blob_path}")
            except Exception as e:
                print(f"  ! no pude borrar {blob_path}: {e}")

        if ok:
            print("\n✅ Smoke test OK")
            return 0
        else:
            print("\n❌ Smoke test FALLÓ")
            return 1


if __name__ == "__main__":
    sys.exit(main())
