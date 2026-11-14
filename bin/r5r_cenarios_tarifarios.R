options(java.parameters = "-Xmx12G")
suppressPackageStartupMessages(library(r5r)); suppressPackageStartupMessages(library(data.table))
B <- path.expand("~/r5_salvador")
core <- build_network(data_path = file.path(B, "dir_ssa_corr"), verbose = FALSE)
fa <- setup_fare_structure(core, base_fare = 5.60, by = "AGENCY_NAME")
cat("=== estrutura por AGENCY_NAME ===\n")
print(as.data.frame(fa$fares_per_type))
cat(sprintf("fares_per_transfer: %d linhas\n", nrow(fa$fares_per_transfer)))
print(utils::head(as.data.frame(fa$fares_per_transfer), 16))

pts <- data.table::fread(file.path(B,"pontos_200.csv")); pts[, id := as.character(id)]
pts <- pts[1:60]

roda <- function(fs, rot, arq) {
  t0 <- Sys.time()
  pf <- pareto_frontier(core, origins=pts, destinations=pts,
        mode=c("WALK","TRANSIT"), mode_egress="WALK",
        departure_datetime=as.POSIXct("11-11-2025 07:00:00", format="%d-%m-%Y %H:%M:%S"),
        time_window=60, percentiles=50, max_trip_duration=180,
        max_walk_time=Inf, walk_speed=3.6, max_rides=8,
        fare_structure=fs, fare_cutoffs=c(5.60, 11.20, 16.80), progress=FALSE)
  cat(sprintf("  %-46s %6d linhas  %5.0f s\n", rot, nrow(pf),
      as.numeric(difftime(Sys.time(), t0, units="secs"))))
  data.table::fwrite(pf, file.path(B, arq))
}

cat("\n=== rodando os tres cenarios ===\n")

# C1: sem integracao nenhuma
c1 <- fa; c1$max_discounted_transfers <- 0L
roda(c1, "C1 sem integracao", "pf_C1.csv")

# C2: integracao so DENTRO do mesmo operador
c2 <- fa
c2$fares_per_transfer[, fare := ifelse(first_leg == second_leg, 5.60, 11.20)]
roda(c2, "C2 integracao so dentro do mesmo operador", "pf_C2.csv")

# C3: integracao plena entre todos, inclusive metro
c3 <- fa
c3$fares_per_transfer[, fare := 5.60]
roda(c3, "C3 integracao plena, inclusive com o metro", "pf_C3.csv")

cat("\nFIM\n")
