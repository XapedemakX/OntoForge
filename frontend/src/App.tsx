import { ToastHost } from './ui'
import { I18nProvider } from './i18n'
import { Shell } from './shell/Shell'
export type { ScreenProps } from './shell/types'
export function App() { return <I18nProvider><ToastHost><Shell /></ToastHost></I18nProvider> }
