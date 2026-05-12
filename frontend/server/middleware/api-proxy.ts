export default defineEventHandler(async (event) => {
  if (!event.path.startsWith('/api/')) {
    return
  }

  const serverHost = process.env.SERVER_HOST
  if (!serverHost) {
    return
  }

  return proxyRequest(event, serverHost + event.path)
})
