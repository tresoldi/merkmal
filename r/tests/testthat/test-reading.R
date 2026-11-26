test_that("spellings of one segment are read as one segment", {
  nfd <- "ã"
  nfc <- "ã"
  pairs <- list(c(nfd, nfc), c("ɡ", "g"), c("tʰʷ", "tʷʰ"), c("ts", "t͡s"),
                c("nd", "ⁿd"), c("ˈa", "a"), c("a⁵⁵", "a˥"), c("ˈt̪/t̪", "t̪"))
  for (p in pairs) {
    expect_equal(distance(p[[1]], p[[2]]), 0, label = paste(p, collapse = " / "))
  }
  expect_identical(normalize("ʧ"), "tʃ")
  expect_identical(unicode_normalize(nfd, "NFC"), nfc)
  expect_identical(unicode_normalize(nfc, "NFD"), nfd)
})

test_that("refusals are diagnosed, not guessed", {
  d <- diagnose(c("tʰ", "pʰ1", "ɑ̠̠", "<?>", "ʷtˢ:ʰ"))
  expect_identical(d$ok, c(TRUE, FALSE, FALSE, FALSE, FALSE))
  expect_identical(d$status[2:4], c("unknown grapheme", "parse error", "source markup, not a sound"))
  expect_identical(d$valid_prefix[c(2, 5)], c("pʰ", "ʷt"))
  expect_identical(d$offending[c(2, 5)], c("1", "ˢ"))
  expect_identical(is_segment(c("tʰ", "pʰ1", "<?>", NA)), c(TRUE, FALSE, FALSE, NA))
})

test_that("a valued system refuses a mark it cannot learn", {
  expect_true(is_segment("kˀ", system = "distinctive"))
  expect_false(is_segment("kˀ", system = "pbase-spe"))
  expect_identical(diagnose("kˀ", system = "pbase-spe")$offending, "ˀ")
  expect_equal(distance("t", "tʰ", system = "phoible"), 0.0394736842, tolerance = 1e-9)
})

test_that("features are sets of labels", {
  f <- get_features(c("p", "b"))
  expect_named(f, c("p", "b"))
  expect_true("voiceless" %in% f$p)
  expect_identical(setdiff(f$p, f$b), "voiceless")
  expect_warning(g <- get_features("pʰ1"), "not read")
  expect_null(g[[1]])
})

test_that("segmentation follows the two policies", {
  expect_identical(segment_ipa("tʃa"), list(c("t", "ʃ", "a")))
  expect_identical(system_segment_ipa(c("tʃa", "kpa")), list(c("tʃ", "a"), c("kp", "a")))
  expect_identical(segment_ipa_merged("tʰoŋ⁵⁵"), list(c("tʰ", "o⁵⁵", "ŋ")))
  expect_identical(merge_tone_digits(c("m", "a", "⁵", "⁵")), c("m", "a⁵⁵"))
  s <- split_tone(c("o⁵⁵", "a"))
  expect_identical(s$base, c("o", "a"))
  expect_identical(s$tone, c("⁵⁵", NA))
  expect_identical(ascii_chao_digits("ma55"), "ma⁵⁵")
})

test_that("feature vectors match the distances", {
  m <- feature_vectors(c("p", "b", "p"), system = "phoible")
  expect_identical(colnames(m), vector_labels("phoible"))
  expect_identical(m[1, ], m[3, ])
  expect_false(identical(m[1, ], m[2, ]))
  expect_warning(v <- feature_vectors("pʰ1"), "not read")
  expect_true(all(is.na(v)))
})
