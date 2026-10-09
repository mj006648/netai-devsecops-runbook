"""Educational local Spark lab; expected results are documented in chapter 11."""

from tempfile import TemporaryDirectory

from pyspark.sql import SparkSession, functions as F, types as T


def main():
    spark = (
        SparkSession.builder.master("local[2]")
        .appName("netai-sensor-textbook")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        schema = T.StructType(
            [
                T.StructField("event_id", T.StringType(), False),
                T.StructField("sensor_id", T.StringType(), False),
                T.StructField("temperature", T.DoubleType(), True),
            ]
        )
        raw = spark.createDataFrame(
            [
                ("e1", "S1", 20.0),
                ("e2", "S1", 22.0),
                ("e3", "S2", 19.0),
                ("e4", "S2", 99.0),
                ("e5", "S3", 23.0),
                ("e6", "S3", None),
            ],
            schema,
        )
        valid = raw.filter(
            F.col("temperature").isNotNull()
            & F.col("temperature").between(-40.0, 60.0)
        )
        locations = spark.createDataFrame(
            [("S1", "north"), ("S2", "south"), ("S3", "west")],
            "sensor_id string, site string",
        )
        summary = valid.groupBy("sensor_id").agg(
            F.count("*").alias("valid_count"),
            F.avg("temperature").alias("avg_temperature"),
        )
        result = summary.join(locations, "sensor_id", "inner")
        print(f"raw_rows={raw.count()}, valid_rows={valid.count()}")
        summary.explain("formatted")
        expected = {
            "S1": ("north", 2, 21.0),
            "S2": ("south", 1, 19.0),
            "S3": ("west", 1, 23.0),
        }
        rows = result.orderBy("sensor_id").collect()
        actual = {
            row.sensor_id: (row.site, row.valid_count, row.avg_temperature)
            for row in rows
        }
        assert len(rows) == 3 and actual == expected, (rows, expected)
        for row in rows:
            print(
                f"{row.sensor_id} site={row.site} "
                f"valid_count={row.valid_count} "
                f"avg_temperature={row.avg_temperature}"
            )
        with TemporaryDirectory(prefix="netai-spark-textbook-") as directory:
            output = f"{directory}/sensor_summary"
            result.write.mode("errorifexists").parquet(output)
            reread = spark.read.parquet(output).orderBy("sensor_id").collect()
            assert reread == rows, (reread, rows)
            print(f"parquet_roundtrip_rows={len(reread)}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
