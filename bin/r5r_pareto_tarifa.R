options(java.parameters = "-Xmx12G")
suppressPackageStartupMessages(library(r5r)); suppressPackageStartupMessages(library(data.table))
B <- path.expand("~/r5_salvador")
core <- build_network(data_path = file.path(B, "dir_ssa"), verbose = FALSE)

cat("=== quantos nomes de agencia o R5 conseguiu resolver? ===\n")
fs <- setup_fare_structure(core, base_fare = 5.60, by = "MODE")
print(table(fs$fares_per_route$agency_name))
cat("  (sao 3 operadores de onibus; o que aparecer aqui mostra o estrago do agency_id)\n")

pts <- data.table::fread(file.path(B, "pontos_200.csv"))
pts[, id := as.character(id)]
pts <- pts[1:60]
cat(sprintf("\npontos: %d  -> %d pares\n", nrow(pts), nrow(pts)^2))

roda <- function(fsx, rotulo) {
  cat(sprintf("\n=== %s ===\n", rotulo))
  t0 <- Sys.time()
  pf <- pareto_frontier(core, origins = pts, destinations = pts,
        mode = c("WALK","TRANSIT"), mode_egress = "WALK",
        departure_datetime = as.POSIXct("11-11-2025 07:00:00", format="%d-%m-%Y %H:%M:%S"),
        time_window = 60, percentiles = 50, max_trip_duration = 180,
        max_walk_time = Inf, walk_speed = 3.6, max_rides = 8,
        fare_structure = fsx, fare_cutoffs = c(5.60, 11.20, 16.80),
        progress = FALSE)
  cat(sprintf("  %d linhas em %.1f s\n", nrow(pf), as.numeric(difftime(Sys.time(), t0, units="secs"))))
  cat("  colunas:", paste(names(pf), collapse=", "), "\n")
  print(utils::head(as.data.frame(pf), 6))
  pf
}

# CENARIO 1: com integracao, como o modelo padrao do r5r propoe
fs1 <- fs
a <- roda(fs1, "CENARIO A: max_discounted_transfers=1, janela 120 min")

# CENARIO 2: sem integracao nenhuma, cada embarque paga de novo
fs2 <- fs
fs2$max_discounted_transfers <- 0L
b <- roda(fs2, "CENARIO B: max_discounted_transfers=0 (sem integracao)")

data.table::fwrite(a, file.path(B, "pareto_A.csv"))
data.table::fwrite(b, file.path(B, "pareto_B.csv"))
cat("\nFIM\n")
