toy <- paste(
  "@format_version 1", "@model toy", "@type categorical",
  "grapheme p consonant voiceless bilabial stop",
  "grapheme t consonant voiceless alveolar stop",
  "grapheme b consonant voiced bilabial stop",
  sep = "\n"
)

test_that("a user model is scored through the same geometry", {
  reg <- mk_registry()
  add_model(reg, toy)
  expect_true("toy" %in% list_systems(registry = reg))
  expect_false("toy" %in% list_systems())
  expect_lt(distance("p", "b", system = "toy", registry = reg),
            distance("p", "t", system = "toy", registry = reg))
  expect_output(print(reg), "toy")
})

test_that("a refused model says why", {
  reg <- mk_registry()
  add_model(reg, toy)
  expect_error(add_model(reg, toy), "already")
  expect_error(add_model(reg, "@model bad\n@type categorical\ngrapheme p nonesuch"), "not added")
  expect_error(add_model(list(), toy), "mk_registry")
})
