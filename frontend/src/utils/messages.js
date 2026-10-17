export const MESSAGE_POLL_INTERVAL_MS = 1800
export const MESSAGE_HISTORY_PAGE_SIZE = 100

export function mergeMessages(current, incoming) {
  const messagesById = new Map(current.map((message) => [message.id, message]))
  incoming.forEach((message) => messagesById.set(message.id, message))
  return [...messagesById.values()].sort((first, second) => first.id - second.id)
}