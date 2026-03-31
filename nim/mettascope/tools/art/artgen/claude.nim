import std/json
import curly, jsony

var
  claudeKey* = ""
let
  claudeUrl = "https://api.anthropic.com/v1/messages"
  claudeModel = "claude-opus-4-6"
  curl = newCurlPool(3)

type
  ConversationMessage* = object
    role*: string
    content*: string
  MessageRequest = object
    model: string
    max_tokens: int
    system: string
    messages: seq[ConversationMessage]

proc last*[T](arr: seq[T], number: int): seq[T] =
  ## Returns the last `number` elements of the array or the whole
  ## array if `number` is greater than the length of the array.
  if number >= arr.len:
    return arr
  return arr[arr.len - number .. ^1]

proc talkToAI*(messages: var seq[ConversationMessage]): string =
  ## Sends messages to the Anthropic Messages API and returns the reply.
  var systemPrompt = ""
  var chatMessages: seq[ConversationMessage]
  for msg in messages:
    if msg.role == "system":
      systemPrompt = msg.content
    else:
      chatMessages.add msg
  let request = MessageRequest(
    model: claudeModel,
    max_tokens: 4096,
    system: systemPrompt,
    messages: chatMessages,
  )
  let response = curl.post(
    claudeUrl,
    @[
      ("x-api-key", claudeKey),
      ("anthropic-version", "2023-06-01"),
      ("Content-Type", "application/json")
    ],
    request.toJson()
  )
  if response.code != 200:
    echo "ERROR: ", response.body
    return
  let data = parseJson(response.body)
  var reply = ""
  for part in data["content"]:
    if part{"type"}.getStr() == "text":
      reply.add part["text"].getStr()
  echo "AI: ", reply
  messages.add(
    ConversationMessage(
      role: "assistant",
      content: reply
    )
  )
  return reply
