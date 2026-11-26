test_that("the package and the linked library have one version", {
  expect_identical(build_info()$version, as.character(utils::packageVersion("merkmal")))
  expect_identical(build_info()$data_profile, "full")
  expect_match(build_info()$unicode_version, "^[0-9]+\\.[0-9]+\\.[0-9]+$")
})

test_that("the seven built-in systems are listed", {
  expect_setequal(
    list_systems(),
    c("descriptive", "distinctive", "phoible", "pbase-hc", "pbase-jfh", "pbase-spe", "pbase-uftc")
  )
  expect_identical(system_kind("distinctive"), "categorical")
  expect_identical(system_kind("phoible"), "valued")
  expect_true("p" %in% system_inventory("distinctive"))
})

test_that("distance is vectorized, recycled and symmetric", {
  expect_equal(distance("p", "b"), 0.125)
  d <- distance("p", c("b", "t", "a"))
  expect_length(d, 3)
  expect_equal(distance(c("b", "t", "a"), "p"), d)
  expect_length(distance(character(), "p"), 0)
  expect_equal(distance("p", "p"), 0)
})

test_that("a refused segment is NA with a warning, never a number", {
  expect_warning(d <- distance(c("p", "pʰ1"), "b"), "not read")
  expect_equal(d[[1]], 0.125)
  expect_true(is.na(d[[2]]))
  expect_true(is.na(suppressWarnings(distance(NA_character_, "b"))))
})

test_that("unknown systems and presets are errors", {
  expect_error(distance("p", "b", system = "nonesuch"), "unknown system")
  expect_error(distance("p", "b", node_weights = "nonesuch"), "unknown weight preset")
  expect_error(distance(1, "b"), "character vector")
})

test_that("coverage and comparability are reported", {
  res <- distance_with_coverage(c("ai", "a"), c("au", "˥"), system = "phoible")
  expect_equal(res$distance, c(0, 1))
  expect_equal(res$coverage[[1]], 23 / 38)
  expect_identical(res$comparability, c("ok", "cross-tier"))
  expect_identical(distance_with_coverage("ai", "au")$coverage, 1)
})

test_that("weight presets change the share of a node", {
  expect_gt(distance("a⁵⁵", "a¹¹"), 0)
  expect_equal(distance("a⁵⁵", "a¹¹", node_weights = "ignore-tone"), 0)
})

test_that("a distance matrix is symmetric and usable for clustering", {
  x <- c("p", "b", "t", "d", "a")
  m <- distance_matrix(x)
  expect_identical(dimnames(m), list(x, x))
  expect_equal(m, t(m))
  expect_equal(unname(diag(m)), rep(0, 5))
  expect_equal(m["p", "b"], distance("p", "b"))
  expect_s3_class(stats::hclust(stats::as.dist(m)), "hclust")
  expect_warning(m2 <- distance_matrix(c("p", "pʰ1")), "not read")
  expect_true(all(is.na(m2[2, ])))
})

test_that("the geometry can be measured directly", {
  expect_identical(feature_distance("voiced", "voiceless"), 2L)
  expect_true(is.na(feature_distance("bilabial", "voiced")))
  expect_equal(
    sound_distance(c("consonant", "voiceless", "bilabial", "stop"), c("consonant", "voiced", "bilabial", "stop")),
    0.3846153846, tolerance = 1e-9
  )
  expect_error(sound_distance("nonesuch", "stop"), "unknown to the geometry")
})
