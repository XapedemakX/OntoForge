import { ToastHost } from './ui'
import { I18nProvider } from './i18n'
import { Shell } from './shell/Shell'
import { GameLauncher } from './game/Launcher'
export type { ScreenProps } from './shell/types'
export function App() { return <I18nProvider><ToastHost><Shell /><GameLauncher /></ToastHost></I18nProvider> }
