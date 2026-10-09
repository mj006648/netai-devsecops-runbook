"""Synthetic micro-batch demonstration; console is a learning sink."""

from tempfile import TemporaryDirectory

from pyspark.sql import SparkSession, functions as F


def main():
    spark = (
        SparkSession.builder.master("local[2]")
        .appName("netai-streaming-textbook")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        events = (
            spark.readStream.format("rate")
            .option("rowsPerSecond", 2)
            .option("numPartitions", 2)
            .load()
            .withColumn("sensor_id", F.concat(F.lit("S"), (F.col("value") % 3 + 1)))
        )
        with TemporaryDirectory(prefix="netai-streaming-textbook-") as directory:
            query = (
                events.writeStream.format("console")
                .outputMode("append")
                .option("truncate", "false")
                .option("checkpointLocation", f"{directory}/checkpoint")
                .trigger(processingTime="2 seconds")
                .start()
            )
            try:
                query.awaitTermination(10)
            finally:
                query.stop()
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
