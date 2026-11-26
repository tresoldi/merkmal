# Digests recorded from the Python package (merkmal 0.11.0), so that the two
# packages identify the same results by the same key.

test_that("the system fingerprint is the library's", {
  fp <- system_fingerprint()
  expect_match(fp$payload, "^schema=merkmal-system-fingerprint-v2\n")
  expect_identical(fp$digest, "3714f6fb12dd35f06251a37f735fc179b5b6cbe72e51739abbc73945f77b8574")
  expect_false(identical(system_fingerprint("phoible")$digest, fp$digest))
})

test_that("operation fingerprints agree with the Python package", {
  expect_identical(operation_fingerprint()$digest,
                   "1588e04fd7a0a15989403dd031895c29d155d7bff9dcbc368ea5ac79c832377b")
  fp <- operation_fingerprint(
    system = "phoible", node_weights = "ignore-tone", tokenization_policy = "system",
    project = "bantu", version = 3L, flags = c("a", "ü"), nested = list(z = TRUE, a = NULL)
  )
  expect_identical(fp$digest, "7c3f3da2d532cfcb4f24d047ecb24f76ba829dbe8c5fd6fbd6318fd1c4ea2fb8")
  expect_match(fp$payload, "^schema=merkmal-operation-fingerprint-v1\n")
})

test_that("ambiguous options are refused", {
  expect_error(operation_fingerprint(version = 3), "integers")
  expect_error(operation_fingerprint("distinctive", NULL, "default", "default", "default", "default", 1L),
               "named")
})

test_that("the SHA-256 is correct across padding boundaries", {
  sha <- function(s) .Call(merkmal:::r_mk_sha256, enc2utf8(s))
  expected <- c(
    "0" = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "55" = "9f4390f8d30c2dd92ec9f095b65e2b9ae9b0a925a5258e241c9f1e910f734318",
    "56" = "b35439a4ac6f0948b6d6f9e3c6af0f5f590ce20f1bde7090ef7970686ec6738a",
    "63" = "7d3e74a05d7db15bce4ad9ec0658ea98e3f06eeecf16b4c6fff2da457ddc2f34",
    "64" = "ffe054fe7ae0cb6dc65c3af9b61d5209f439851db43d0ba5997337df154668eb",
    "65" = "635361c48bb9eab14198e76ea8ab7f1a41685d6ad62aa9146d301d4f17eb0ae0",
    "119" = "31eba51c313a5c08226adf18d4a359cfdfd8d2e816b13f4af952f7ea6584dcfb",
    "120" = "2f3d335432c70b580af0e8e1b3674a7c020d683aa5f73aaaedfdc55af904c21c",
    "200" = "c2a908d98f5df987ade41b5fce213067efbcc21ef2240212a41e54b5e7c28ae5"
  )
  for (n in names(expected)) {
    expect_identical(sha(strrep("a", as.integer(n))), expected[[n]], label = paste("length", n))
  }
  expect_identical(sha("abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
  expect_identical(sha("ɑ̠ test"), "3452536727817cd1ed8bd2d9c728570a84357f35658e0ca2a323e96750745818")
})
