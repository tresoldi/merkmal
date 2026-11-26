# The golden fixtures of the C test suite, copied by tools/sync_r_sources.py:
# the R package must return the library's contract values exactly.

read_golden <- function(name) {
  path <- test_path("golden", name)
  utils::read.delim(path, quote = "", na.strings = character(), colClasses = "character",
                    encoding = "UTF-8", stringsAsFactors = FALSE)
}

systems <- c("descriptive", "distinctive", "phoible", "pbase-hc", "pbase-jfh", "pbase-spe", "pbase-uftc")

for (system in systems) {
  test_that(paste("golden distances:", system), {
    g <- read_golden(paste0(system, "_distances.tsv"))
    expect_gt(nrow(g), 0)
    got <- distance(g$GRAPHEME_A, g$GRAPHEME_B, system = system)
    expected <- as.numeric(g$DISTANCE)
    # The fixtures are rounded to ten decimal places.
    off <- which(is.na(got) | abs(got - expected) > 1e-10)
    expect_identical(off, integer(0), label = paste(system, "pairs off the fixtures"))
  })
}

for (system in c("descriptive", "distinctive")) {
  test_that(paste("golden features:", system), {
    g <- read_golden(paste0(system, "_features.tsv"))
    got <- get_features(g$GRAPHEME, system = system)
    expected <- lapply(strsplit(g$FEATURES, "|", fixed = TRUE), sort, method = "radix")
    expect_identical(unname(got), expected)
  })
}
