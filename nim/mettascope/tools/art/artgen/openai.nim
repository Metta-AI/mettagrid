import std/[strutils, json, base64, os]
import curly, jsony

var
  aiKey* = ""
let
  aiResponsesUrl = "https://api.openai.com/v1/responses"
  aiTextModel = "gpt-5.1-codex"
  curl = newCurlPool(3)

const
  ImageRequestRetryCount = 3
  ImageRequestRetryDelayMs = 1500
  OpenAiTimeoutSeconds = (60 * 3).float32 # 3 min

type
  OpenAiError* = object of CatchableError

  ConversationMessage* = object
    role*: string
    content*: string

  ResponseRequest = ref object
    model: string
    input: seq[ConversationMessage]

proc getImageResult(data: JsonNode): string =
  ## Gets the first image generation result as a base64 string.
  for item in data["output"]:
    if item{"type"}.getStr() == "image_generation_call":
      let image64 = item{"result"}.getStr()
      if image64.len > 0:
        return image64
  raise newException(
    OpenAiError,
    "OpenAI response did not contain image_generation_call data."
  )

proc last*[T](arr: seq[T], number: int): seq[T] =
  ## Returns the last `number` elements of the array `arr` or the whole
  ## array if `number` is greater than the length of the array.
  if number >= arr.len:
    return arr
  return arr[arr.len - number .. ^1]

proc talkToAI*(messages: var seq[ConversationMessage]): string =
  ## Sends messages to the OpenAI Responses API and returns the reply.
  let request = ResponseRequest(
    model: aiTextModel,
    input: messages,
  )
  let response = curl.post(
    aiResponsesUrl,
    @[
      ("Authorization", "Bearer " & aiKey),
      ("Content-Type", "application/json")
    ],
    request.toJson(),
    OpenAiTimeoutSeconds
  )
  if response.code != 200:
    echo "ERROR: ", response.body
    return
  let data = parseJson(response.body)
  var reply = ""
  for item in data["output"]:
    if item{"type"}.getStr() == "message":
      for part in item["content"]:
        if part{"type"}.getStr() == "output_text":
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
  size = "1024x1024",
  quality = "high",
  background = "transparent",
  outputFormat = "png",
  inputFidelity = "high",
  action = "edit"
): string =
  ## Creates an image and returns the PNG bytes.
  if verbose:
    let pathText = if inspirationPath.len > 0: inspirationPath else: "<memory>"
    echo "[openai] Sending inspiration image: ", pathText,
      " (", inspirationImagePng.len, " bytes)"

  if aiKey.len == 0:
    raise newException(OpenAiError, "OpenAI API key is empty.")
  if model.len == 0:
    raise newException(OpenAiError, "OpenAI image model must not be empty.")
  let modelName = model.toLowerAscii()
  if modelName.contains("dall-e"):
    raise newException(OpenAiError, "DALL-E models are not allowed.")
  if modelName.startsWith("gpt-image"):
    raise newException(
      OpenAiError,
      "OpenAI Responses API expects a mainline model " &
      "(for example gpt-4.1 or gpt-5), not " & model & "."
    )
  if prompt.len == 0:
    raise newException(OpenAiError, "OpenAI image prompt must not be empty.")
  if inspirationImagePng.len == 0:
    raise newException(
      OpenAiError,
      "OpenAI inspiration image payload must not be empty."
    )

  let inspirationB64 = encode(inspirationImagePng)
  let requestBody = %*{
    "model": model,
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "input_text",
            "text": prompt
          },
          {
            "type": "input_image",
            "image_url": "data:image/png;base64," & inspirationB64
          }
        ]
      }
    ],
    "tool_choice": {
      "type": "image_generation"
    },
    "tools": [
      {
        "type": "image_generation",
        "action": action,
        "size": size,
        "quality": quality,
        "background": background,
        "output_format": outputFormat,
        "input_fidelity": inputFidelity
      }
    ]
  }
  var lastErrorMessage = ""
  for attempt in 1 .. ImageRequestRetryCount:
    try:
      let response = curl.post(
        aiResponsesUrl,
        @[
          ("Authorization", "Bearer " & aiKey),
          ("Content-Type", "application/json")
        ],
        $requestBody,
        OpenAiTimeoutSeconds
      )
      if response.code != 200:
        raise newException(
          OpenAiError,
          "OpenAI image generation failed with HTTP " &
          $response.code & ": " & response.body
        )

      let data = parseJson(response.body)
      let image64 = getImageResult(data)
      return decode(image64)
    except OpenAiError:
      raise
    except CatchableError as err:
      lastErrorMessage = err.msg
      if attempt < ImageRequestRetryCount:
        sleep(ImageRequestRetryDelayMs)

  raise newException(
    OpenAiError,
    "OpenAI image request failed after " &
    $ImageRequestRetryCount & " attempts: " & lastErrorMessage
  )
