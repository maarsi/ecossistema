options(java.parameters = "-Xmx8G")
suppressPackageStartupMessages(library(r5r)); suppressPackageStartupMessages(library(data.table))
B <- path.expand("~/r5_salvador")
core <- build_network(data_path = file.path(B, "dir_r5r"), verbose = FALSE)
pts <- data.table::fread(file.path(B, "pontos_200.csv")); pts[, id := as.character(id)]
roda <- function(mr) {
  t0 <- Sys.time()
  x <- travel_time_matrix(core, origins = pts, destinations = pts,
        mode = c("WALK","TRANSIT"), mode_egress = "WALK",
        departure_datetime = as.POSIXct("11-11-2025 07:00:00", format="%d-%m-%Y %H:%M:%S"),
        time_window = 60, percentiles = 50, max_trip_duration = 300,
        max_walk_time = Inf, walk_speed = 3.6, max_rides = mr, progress = FALSE)
  list(x = x, s = as.numeric(difftime(Sys.time(), t0, units = "secs")))
}
cat("=== tempo, tres repeticoes com max_rides=8 ===\n")
for (i in 1:3) { r <- roda(8); cat(sprintf("  repeticao %d: %.1f s\n", i, r$s)) }
data.table::fwrite(r$x, file.path(B, "matriz_r5r_8.csv"))
cat("gravado\n")
