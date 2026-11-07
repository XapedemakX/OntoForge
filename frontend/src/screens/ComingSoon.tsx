import { EmptyState } from '../kit'
import { useT } from '../i18n'
export function ComingSoon({ titleKey }: { titleKey: string }) {
  const t = useT()
  return <div className="page"><h1>{t(titleKey)}</h1><EmptyState pose="reflechit" title={t('common.soon')} /></div>
}
