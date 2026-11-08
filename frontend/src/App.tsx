import { ToastHost } from './ui'
import { I18nProvider } from './i18n'
import { Shell } from './shell/Shell'
import { GameLauncher } from './game/Launcher'
import { AuthGate } from './auth/AuthGate'
export type { ScreenProps } from './shell/types'
export function App() { return <I18nProvider><AuthGate><ToastHost><Shell /><GameLauncher /></ToastHost></AuthGate></I18nProvider> }
