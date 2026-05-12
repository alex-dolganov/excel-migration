export function shouldRenderInitCard({ isInit, initError, initStage }) {
  return isInit || Boolean(initError) || initStage !== 'idle'
}

export function getInitStageDescription(initStage) {
  switch (initStage) {
    case 'frame':
      return 'Connecting to the Bitrix24 frame.'
    case 'app-init':
      return 'Initializing application data inside Bitrix24.'
    case 'title':
      return 'Finalizing application shell.'
    case 'error':
      return 'Application startup failed.'
    default:
      return 'Preparing application startup.'
  }
}
