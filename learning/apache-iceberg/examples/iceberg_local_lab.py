#!/usr/bin/env python3
"""Run and verify the CPU-only Apache Iceberg local lab.

The script uses Spark's local master and Iceberg's HadoopCatalog. It does not
need Docker, S3, Hive Metastore, or a running Hadoop cluster.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse

from pyspark.sql import SparkSession


ICEBERG_VERSION = "1.12.0"
SPARK_RUNTIME = "4.0_2.13"
ICEBERG_PACKAGE = (
    f"org.apache.iceberg:iceberg-spark-runtime-{SPARK_RUNTIME}:{ICEBERG_VERSION}"
)
TABLE = "local.lab.orders"
DEFAULT_WAREHOUSE = Path("/tmp/netai-iceberg-lab/warehouse")
WAREHOUSE_MARKER = ".netai-iceberg-local-lab"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--warehouse",
        type=Path,
        default=DEFAULT_WAREHOUSE,
        help="local HadoopCatalog warehouse (default: %(default)s)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help=(
            "preserve other files in an existing lab warehouse; "
            "local.lab.orders is still dropped and recreated"
        ),
    )
    return parser.parse_args()


def build_spark(warehouse: Path) -> SparkSession:
    return (
        SparkSession.builder.appName("iceberg-local-lab")
        .master("local[2]")
        .config("spark.jars.packages", ICEBERG_PACKAGE)
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.local.type", "hadoop")
        .config("spark.sql.catalog.local.warehouse", warehouse.resolve().as_uri())
        .config("spark.sql.defaultCatalog", "local")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.memory", "1g")
        .getOrCreate()
    )


def rows(spark: SparkSession, query: str) -> list[tuple]:
    return [tuple(row) for row in spark.sql(query).collect()]


def scalar(spark: SparkSession, query: str):
    result = rows(spark, query)
    assert len(result) == 1 and len(result[0]) == 1, result
    return result[0][0]


def snapshot_id(spark: SparkSession) -> int:
    return int(
        scalar(
            spark,
            f"SELECT snapshot_id FROM {TABLE}.snapshots ORDER BY committed_at DESC LIMIT 1",
        )
    )


def assert_rows(spark: SparkSession, query: str, expected: list[tuple]) -> None:
    actual = rows(spark, query)
    assert actual == expected, f"query={query!r}\nexpected={expected!r}\nactual={actual!r}"


def metadata_json_path(spark: SparkSession) -> Path:
    uri = scalar(
        spark,
        f"SELECT file FROM {TABLE}.metadata_log_entries ORDER BY timestamp DESC LIMIT 1",
    )
    parsed = urlparse(uri)
    if parsed.scheme not in ("", "file"):
        raise AssertionError(f"expected local metadata URI, got {uri}")
    return Path(unquote(parsed.path))


def current_field_ids(spark: SparkSession) -> dict[str, int]:
    metadata = json.loads(metadata_json_path(spark).read_text(encoding="utf-8"))
    current_id = metadata["current-schema-id"]
    schema = next(item for item in metadata["schemas"] if item["schema-id"] == current_id)
    return {field["name"]: int(field["id"]) for field in schema["fields"]}


def show(spark: SparkSession, title: str, query: str) -> None:
    print(f"\n=== {title} ===")
    spark.sql(query).show(truncate=False)


def run_v2_lab(spark: SparkSession) -> tuple[int, dict[str, int]]:
    spark.sql("CREATE NAMESPACE IF NOT EXISTS local.lab")
    spark.sql(f"DROP TABLE IF EXISTS {TABLE}")
    spark.sql(
        f"""
        CREATE TABLE {TABLE} (
          id BIGINT NOT NULL,
          customer STRING,
          status STRING,
          amount DECIMAL(10, 2),
          ordered_at TIMESTAMP
        )
        USING iceberg
        PARTITIONED BY (days(ordered_at))
        TBLPROPERTIES (
          'format-version'='2',
          'write.delete.mode'='merge-on-read',
          'write.update.mode'='merge-on-read',
          'write.merge.mode'='merge-on-read'
        )
        """
    )
    spark.sql(
        f"""
        INSERT INTO {TABLE} VALUES
          (1, '서울상점', 'pending', 100.00, TIMESTAMP '2026-01-10 09:00:00'),
          (2, '부산상점', 'pending', 200.00, TIMESTAMP '2026-01-11 10:00:00'),
          (3, '서울상점', 'paid',    150.00, TIMESTAMP '2026-02-01 11:00:00')
        """
    )
    first_snapshot = snapshot_id(spark)
    assert_rows(
        spark,
        f"SELECT id, status FROM {TABLE} ORDER BY id",
        [(1, "pending"), (2, "pending"), (3, "paid")],
    )

    spark.sql(
        f"""
        INSERT INTO {TABLE} VALUES
          (4, '인천상점', 'pending', 80.00,  TIMESTAMP '2026-02-02 12:00:00'),
          (5, '부산상점', 'paid',    300.00, TIMESTAMP '2026-03-03 13:00:00')
        """
    )
    spark.sql(
        f"UPDATE {TABLE} SET status='paid', amount=110.00 WHERE id=1"
    )
    spark.sql(f"DELETE FROM {TABLE} WHERE id=2")
    spark.sql(
        f"""
        MERGE INTO {TABLE} AS target
        USING (
          SELECT * FROM VALUES
            (3L, 'shipped', CAST(175.00 AS DECIMAL(10, 2))),
            (6L, 'pending', CAST(120.00 AS DECIMAL(10, 2)))
          AS source(id, status, amount)
        ) AS source
        ON target.id = source.id
        WHEN MATCHED THEN UPDATE SET
          target.status = source.status,
          target.amount = source.amount
        WHEN NOT MATCHED THEN INSERT
          (id, customer, status, amount, ordered_at)
          VALUES (source.id, '신규상점', source.status, source.amount,
                  TIMESTAMP '2026-03-04 14:00:00')
        """
    )
    assert_rows(
        spark,
        f"SELECT id, status, CAST(amount AS STRING) FROM {TABLE} ORDER BY id",
        [
            (1, "paid", "110.00"),
            (3, "shipped", "175.00"),
            (4, "pending", "80.00"),
            (5, "paid", "300.00"),
            (6, "pending", "120.00"),
        ],
    )

    before_rename = current_field_ids(spark)
    amount_id = before_rename["amount"]
    spark.sql(f"ALTER TABLE {TABLE} RENAME COLUMN amount TO total_amount")
    after_rename = current_field_ids(spark)
    assert "amount" not in after_rename
    assert after_rename["total_amount"] == amount_id

    spark.sql(f"ALTER TABLE {TABLE} ADD PARTITION FIELD bucket(4, id)")
    spark.sql(
        f"""
        INSERT INTO {TABLE} VALUES
          (7, '대전상점', 'paid', 70.00, TIMESTAMP '2026-04-05 15:00:00')
        """
    )
    spec_counts = rows(
        spark,
        f"SELECT spec_id, count(*) FROM {TABLE}.files GROUP BY spec_id ORDER BY spec_id",
    )
    assert len(spec_counts) >= 2, f"partition evolution not visible: {spec_counts}"
    assert len({spec_id for spec_id, _ in spec_counts}) >= 2, spec_counts

    assert_rows(
        spark,
        f"SELECT id FROM {TABLE} VERSION AS OF {first_snapshot} ORDER BY id",
        [(1,), (2,), (3,)],
    )
    assert int(scalar(spark, f"SELECT count(*) FROM {TABLE}.snapshots")) >= 6

    show(spark, "v2 최종 행", f"SELECT * FROM {TABLE} ORDER BY id")
    show(
        spark,
        "스냅샷 계보",
        f"SELECT committed_at, snapshot_id, parent_id, operation FROM {TABLE}.snapshots ORDER BY committed_at",
    )
    show(
        spark,
        "파티션 명세별 현재 데이터 파일",
        f"SELECT spec_id, count(*) AS files, sum(record_count) AS records FROM {TABLE}.files GROUP BY spec_id ORDER BY spec_id",
    )
    print(f"\nfield ID 보존 확인: amount({amount_id}) -> total_amount({after_rename['total_amount']})")
    print(f"time travel 확인: snapshot {first_snapshot}에는 id 1, 2, 3만 존재")
    return first_snapshot, after_rename


def run_v3_lab(spark: SparkSession) -> None:
    spark.sql(f"ALTER TABLE {TABLE} SET TBLPROPERTIES ('format-version'='3')")
    format_property = rows(
        spark, f"SHOW TBLPROPERTIES {TABLE} ('format-version')"
    )
    assert format_property == [("format-version", "3")], format_property

    spark.sql(
        f"""
        INSERT INTO {TABLE} VALUES
          (8, '광주상점', 'pending', 88.00, TIMESTAMP '2026-04-06 16:00:00')
        """
    )
    lineage_before = rows(
        spark,
        f"SELECT id, _row_id, _last_updated_sequence_number FROM {TABLE} WHERE id=8",
    )
    assert len(lineage_before) == 1
    assert lineage_before[0][1] is not None
    assert lineage_before[0][2] is not None

    row_id_before = lineage_before[0][1]
    spark.sql(f"UPDATE {TABLE} SET status='paid' WHERE id=8")
    lineage_after = rows(
        spark,
        f"SELECT id, _row_id, _last_updated_sequence_number FROM {TABLE} WHERE id=8",
    )
    assert lineage_after[0][1] == row_id_before
    assert lineage_after[0][2] > lineage_before[0][2]

    spark.sql(f"DELETE FROM {TABLE} WHERE id=4")
    assert scalar(spark, f"SELECT count(*) FROM {TABLE} WHERE id=4") == 0
    delete_files = rows(
        spark,
        f"""
        SELECT content, file_path, record_count, referenced_data_file,
               content_offset, content_size_in_bytes
        FROM {TABLE}.all_delete_files
        ORDER BY file_path
        """,
    )
    assert delete_files, "v3 merge-on-read DELETE did not create a delete artifact"
    assert any(
        str(file_path).endswith(".puffin")
        and record_count == 1
        and referenced_data_file is not None
        and content_offset is not None
        and content_size is not None
        for _, file_path, record_count, referenced_data_file, content_offset, content_size
        in delete_files
    ), f"expected a deletion vector, got {delete_files}"

    show(
        spark,
        "v3 row lineage",
        f"SELECT id, _row_id, _last_updated_sequence_number FROM {TABLE} ORDER BY id",
    )
    show(
        spark,
        "v3 deletion vector",
        f"""SELECT content, file_path, record_count, referenced_data_file,
                   content_offset, content_size_in_bytes
            FROM {TABLE}.all_delete_files""",
    )
    print("\nv3 확인: format-version=3, 새 행의 lineage 존재, UPDATE 뒤 row ID 보존, DV 생성")


def main() -> int:
    args = parse_args()
    warehouse = args.warehouse.expanduser().resolve()
    protected = {Path("/"), Path.home().resolve(), Path.cwd().resolve()}
    if warehouse in protected:
        raise SystemExit(f"안전하지 않은 warehouse 경로를 거부합니다: {warehouse}")
    if warehouse.exists():
        if not warehouse.is_dir():
            raise SystemExit(f"warehouse 경로가 디렉터리가 아닙니다: {warehouse}")
        marker = warehouse / WAREHOUSE_MARKER
        is_nonempty = next(warehouse.iterdir(), None) is not None
        if not marker.is_file() and is_nonempty:
            raise SystemExit(
                "기존 warehouse에는 실습 marker가 없어 변경하지 않습니다: "
                f"{warehouse}"
            )
    if warehouse.exists() and not args.keep:
        shutil.rmtree(warehouse)
    warehouse.mkdir(parents=True, exist_ok=True)
    (warehouse / WAREHOUSE_MARKER).touch()

    print(f"Iceberg package: {ICEBERG_PACKAGE}")
    print(f"warehouse: {warehouse}")
    spark = build_spark(warehouse)
    spark.sparkContext.setLogLevel("WARN")
    try:
        print(f"Spark: {spark.version}")
        run_v2_lab(spark)
        run_v3_lab(spark)
        print("\nALL ASSERTIONS PASSED")
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
