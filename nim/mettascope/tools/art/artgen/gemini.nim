import std/[json, base64, os]
import curly

var
  geminiKey* = ""
let
  geminiModel = "gemini-2.5-flash"
  curl = newCurlPool(3)

const
  ImageRequestRetryCount = 3
  ImageRequestRetryDelayMs = 1500
  GeminiTimeoutSeconds = (60 * 3).float32 # 3 min

type
  GeminiError* = object of CatchableError

  ConversationMessage* = object
    role*: string
    content*: string

proc imageUrl(model: string): string =
  ## Builds the Gemini endpoint URL for a specific model.
  return "https://generativelanguage.googleapis.com/v1beta/models/" &
    model & ":generateContent?key=" & geminiKey

proc getImageResult(data: JsonNode): string =
  ## Gets the first image generation result as a base64 string.
  if data.hasKey("candidates"):
    for candidate in data["candidates"]:
      let parts = candidate{"content"}{"parts"}
      if parts.kind == JArray:
        for part in parts:
          let image64 = part{"inlineData"}{"data"}.getStr()
          if image64.len > 0:
            return image64
  raise newException(
    GeminiError,
    "Gemini response did not contain image inlineData."
  )

proc last*[T](arr: seq[T], number: int): seq[T] =
  ## Returns the last `number` elements of the array or the whole
  ## array if `number` is greater than the length of the array.
  if number >= arr.len:
    return arr
  return arr[arr.len - number .. ^1]

proc talkToAI*(messages: var seq[ConversationMessage]): string =
  ## Sends messages to the Gemini generateContent API and returns the reply.
  var systemText = ""
  var contents = newJArray()
  for msg in messages:
    if msg.role == "system":
      systemText = msg.content
    else:
      let role = if msg.role == "assistant": "model" else: msg.role
      contents.add(%*{"role": role, "parts": [{"text": msg.content}]})
  var body = %*{"contents": contents}
  if systemText.len > 0:
    body["systemInstruction"] = %*{"parts": [{"text": systemText}]}
  let response = curl.post(
    imageUrl(geminiModel),
    @[("Content-Type", "application/json")],
    $body,
    GeminiTimeoutSeconds
  )
  if response.code != 200:
    echo "ERROR: ", response.body
    return
  let data = parseJson(response.body)
  var reply = ""
  for part in data["candidates"][0]["content"]["parts"]:
    if part.hasKey("text"):
      reply.add part["text"].getStr()
  echo "AI: ", reply
  messages.add(
    ConversationMessage(
      role: "assistant",
      content: reply
    )
  )
  return reply

proc createImage*(
  model: string,
  prompt: string,
  inspirationImagePng: string,
  inspirationPath = "",
  verbose = false,
  aspectRatio = "1:1"
): string =
  ## Creates an image and returns PNG/JPEG bytes.
  if verbose:
    let pathText = if inspirationPath.len > 0: inspirationPath else: "<memory>"
    echo "[gemini] Sending inspiration image: ", pathText,
      " (", inspirationImagePng.len, " bytes)"

  if geminiKey.len == 0:
    raise newException(GeminiError, "Gemini API key is empty.")
  if model.len == 0:
    raise newException(GeminiError, "Gemini image model must not be empty.")
  if prompt.len == 0:
    raise newException(GeminiError, "Gemini image prompt must not be empty.")
  if inspirationImagePng.len == 0:
    raise newException(
      GeminiError,
      "Gemini inspiration image payload must not be empty."
    )
  if aspectRatio.len == 0:
    raise newException(
      GeminiError,
      "Gemini image aspect ratio must not be empty."
    )

  let requestBody = %*{
    "contents": [
      {
        "role": "user",
        "parts": [
          {
            "text": prompt
          },
          {
            "inline_data": {
              "mime_type": "image/png",
              "data": encode(inspirationImagePng)
            }
          }
        ]
      }
    ],
    "generationConfig": {
      "responseModalities": ["TEXT", "IMAGE"],
      "imageConfig": {
        "aspectRatio": aspectRatio
      }
    }
  }

  var lastErrorMessage = ""
  for attempt in 1 .. ImageRequestRetryCount:
    try:
      let response = curl.post(
        imageUrl(model),
        @[("Content-Type", "application/json")],
        $requestBody,
        GeminiTimeoutSeconds
      )
      if response.code != 200:
        raise newException(
          GeminiError,
          "Gemini image generation failed with HTTP " &
          $response.code & ": " & response.body
        )
      let data = parseJson(response.body)
      let image64 = getImageResult(data)
      return decode(image64)
    except GeminiError:
      raise
    except CatchableError as err:
      lastErrorMessage = err.msg
      if attempt < ImageRequestRetryCount:
        sleep(ImageRequestRetryDelayMs)

  raise newException(
    GeminiError,
    "Gemini image request failed after " &
    $ImageRequestRetryCount & " attempts: " & lastErrorMessage
  )
