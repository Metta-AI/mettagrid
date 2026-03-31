import std/[json, base64, os]
import curly, jsony

var
  xaiKey* = ""
let
  xaiUrl = "https://api.x.ai/v1/chat/completions"
  xaiImageEditsUrl = "https://api.x.ai/v1/images/edits"
  xaiModel = "grok-4-latest"
  curl = newCurlPool(3)

const
  ImageRequestRetryCount = 3
  ImageRequestRetryDelayMs = 1500
  XaiTimeoutSeconds = (60 * 3).float32 # 3 min

type
  XaiError* = object of CatchableError

  ConversationMessage* = object
    role*: string
    content*: string
  ChatRequest = object
    model: string
    messages: seq[ConversationMessage]
    stream: bool
    temperature: float
  Completion = object
    index: int
    message: ConversationMessage
    finishReason: string
  CompletionsResponse = object
    choices: seq[Completion]

proc getImageResult(data: JsonNode): string =
  ## Gets the first image generation result as a base64 string.
  if data.hasKey("data"):
    for item in data["data"]:
      let image64 = item{"b64_json"}.getStr()
      if image64.len > 0:
        return image64
  raise newException(
    XaiError,
    "xAI response did not contain data[0].b64_json image data."
  )

proc last*[T](arr: seq[T], number: int): seq[T] =
  ## Returns the last `number` elements of the array or the whole
  ## array if `number` is greater than the length of the array.
  if number >= arr.len:
    return arr
  return arr[arr.len - number .. ^1]

proc talkToAI*(messages: var seq[ConversationMessage]): string =
  ## Sends messages to the xAI chat completions API and returns the reply.
  let request = ChatRequest(
    model: xaiModel,
    messages: messages,
    stream: false,
    temperature: 0.7,
  )
  let response = curl.post(
    xaiUrl,
    @[
      ("Authorization", "Bearer " & xaiKey),
      ("Content-Type", "application/json")
    ],
    request.toJson(),
    XaiTimeoutSeconds
  )
  if response.code != 200:
    echo "ERROR: ", response.body
    return
  let data = response.body.fromJson(CompletionsResponse)
  let reply = data.choices[0].message.content
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
  resolution = "2k",
  aspectRatio = "1:1"
): string =
  ## Creates an image and returns the PNG/JPEG bytes.
  if verbose:
    let pathText = if inspirationPath.len > 0: inspirationPath else: "<memory>"
    echo "[xai] Sending inspiration image: ", pathText,
      " (", inspirationImagePng.len, " bytes)"

  if xaiKey.len == 0:
    raise newException(XaiError, "xAI API key is empty.")
  if model.len == 0:
    raise newException(XaiError, "xAI image model must not be empty.")
  if prompt.len == 0:
    raise newException(XaiError, "xAI image prompt must not be empty.")
  if inspirationImagePng.len == 0:
    raise newException(
      XaiError,
      "xAI inspiration image payload must not be empty."
    )

  let imageDataUri = "data:image/png;base64," & encode(inspirationImagePng)
  var requestBody = %*{
    "model": model,
    "prompt": prompt,
    "image": {
      "url": imageDataUri,
      "type": "image_url"
    },
    "response_format": "b64_json",
    "aspect_ratio": aspectRatio
  }
  if resolution.len > 0:
    requestBody["resolution"] = %resolution

  var lastErrorMessage = ""
  for attempt in 1 .. ImageRequestRetryCount:
    try:
      let response = curl.post(
        xaiImageEditsUrl,
        @[
          ("Authorization", "Bearer " & xaiKey),
          ("Content-Type", "application/json")
        ],
        $requestBody,
        XaiTimeoutSeconds
      )
      if response.code != 200:
        raise newException(
          XaiError,
          "xAI image generation failed with HTTP " &
          $response.code & ": " & response.body
        )
      let data = parseJson(response.body)
      let image64 = getImageResult(data)
      return decode(image64)
    except XaiError:
      raise
    except CatchableError as err:
      lastErrorMessage = err.msg
      if attempt < ImageRequestRetryCount:
        sleep(ImageRequestRetryDelayMs)

  raise newException(
    XaiError,
    "xAI image request failed after " &
    $ImageRequestRetryCount & " attempts: " & lastErrorMessage
  )
