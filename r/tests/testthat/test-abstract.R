test_that("an abstract segment is bounded over its completions", {
  p <- abstract_segment_from_grapheme("p")
  b <- abstract_segment_from_grapheme("b")
  exact <- compare_abstract(p, b)
  expect_equal(exact$distance, distance("p", "b"))
  expect_equal(exact$minimum, exact$maximum)
  place <- c("labial", "coronal", "dorsal", "labial_place", "coronal_place", "dorsal_place",
             "anterior", "distributed")
  unknown <- do.call(with_cells, c(list(p), stats::setNames(as.list(rep("*", length(place))), place)))
  cmp <- compare_abstract(unknown, b)
  expect_lte(cmp$minimum, cmp$distance)
  expect_lte(cmp$distance, cmp$maximum)
  expect_identical(is_compatible(unknown, c("t", "k", "b", "a")), c(TRUE, TRUE, FALSE, FALSE))
  expect_true(all(c("p", "t", "k") %in% compatible_graphemes(unknown)))
})

test_that("with_cells returns a new segment and leaves the old one", {
  p <- abstract_segment_from_grapheme("p")
  before <- as.character(p)
  q <- with_cells(p, voice = "+")
  expect_identical(as.character(p), before)
  expect_identical(cells(q)[["voice"]], "+")
  expect_true("+" %in% column_values(p, "voice"))
  expect_error(with_cells(p, nonesuch = "+"), "nonesuch")
  expect_identical(as.character(abstract_segment(as.character(p))), before)
})

test_that("segments outlive the registry object that made them", {
  make <- function() {
    reg <- mk_registry()
    add_model(reg, paste("@model toy", "@type categorical",
                         "grapheme p consonant voiceless bilabial stop", sep = "\n"))
    abstract_segment_from_grapheme("p", system = "toy", registry = reg)
  }
  seg <- make()
  gc()
  gc()
  expect_match(as.character(seg), "voice=-")
  rm(seg)
  expect_silent(gc())
})
