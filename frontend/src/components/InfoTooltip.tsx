import { type CSSProperties, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

interface InfoTooltipProps {
  label: string
  children: string
}

const VIEWPORT_MARGIN = 12
const GAP = 8

export function InfoTooltip({ label, children }: InfoTooltipProps) {
  const descriptionId = useId()
  const triggerRef = useRef<HTMLSpanElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [pinned, setPinned] = useState(false)
  const [style, setStyle] = useState<CSSProperties>({ top: 0, left: 0 })

  useLayoutEffect(() => {
    if (!open || !triggerRef.current || !popoverRef.current) return
    const trigger = triggerRef.current.getBoundingClientRect()
    const popover = popoverRef.current.getBoundingClientRect()
    const left = Math.min(
      Math.max(trigger.left + trigger.width / 2 - popover.width / 2, VIEWPORT_MARGIN),
      window.innerWidth - popover.width - VIEWPORT_MARGIN,
    )
    const above = trigger.top - popover.height - GAP
    const top = above >= VIEWPORT_MARGIN
      ? above
      : Math.min(trigger.bottom + GAP, window.innerHeight - popover.height - VIEWPORT_MARGIN)
    setStyle({ top: Math.max(top, VIEWPORT_MARGIN), left: Math.max(left, VIEWPORT_MARGIN) })
  }, [children, open])

  useEffect(() => {
    if (!open) return
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setPinned(false)
        setOpen(false)
        triggerRef.current?.focus()
      }
    }
    function closeOutside(event: PointerEvent) {
      const target = event.target as Node
      if (!triggerRef.current?.contains(target) && !popoverRef.current?.contains(target)) {
        setPinned(false)
        setOpen(false)
      }
    }
    function reposition() {
      const trigger = triggerRef.current
      const popover = popoverRef.current
      if (!trigger || !popover) return
      const triggerBox = trigger.getBoundingClientRect()
      const popoverBox = popover.getBoundingClientRect()
      const left = Math.min(
        Math.max(triggerBox.left + triggerBox.width / 2 - popoverBox.width / 2, VIEWPORT_MARGIN),
        window.innerWidth - popoverBox.width - VIEWPORT_MARGIN,
      )
      const above = triggerBox.top - popoverBox.height - GAP
      const top = above >= VIEWPORT_MARGIN ? above : triggerBox.bottom + GAP
      setStyle({ top: Math.max(top, VIEWPORT_MARGIN), left: Math.max(left, VIEWPORT_MARGIN) })
    }
    document.addEventListener('keydown', closeOnEscape)
    document.addEventListener('pointerdown', closeOutside)
    window.addEventListener('resize', reposition)
    window.addEventListener('scroll', reposition, true)
    return () => {
      document.removeEventListener('keydown', closeOnEscape)
      document.removeEventListener('pointerdown', closeOutside)
      window.removeEventListener('resize', reposition)
      window.removeEventListener('scroll', reposition, true)
    }
  }, [open])

  return (
    <span className="info-tooltip">
      <span
        ref={triggerRef}
        className="info-tooltip__trigger"
        role="button"
        tabIndex={0}
        aria-label={label}
        aria-expanded={open}
        aria-describedby={open ? descriptionId : undefined}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => setPinned((value) => {
          const next = !value
          setOpen(next)
          return next
        })}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            setPinned((value) => {
              const next = !value
              setOpen(next)
              return next
            })
          }
        }}
        onMouseEnter={() => { if (!pinned) setOpen(true) }}
        onMouseLeave={() => { if (!pinned) setOpen(false) }}
        onFocus={() => { if (!pinned) setOpen(true) }}
        onBlur={() => { if (!pinned) setOpen(false) }}
      >
        <span aria-hidden="true">i</span>
      </span>
      {open
        ? createPortal(
            <div
              ref={popoverRef}
              className="info-tooltip__content"
              id={descriptionId}
              role="tooltip"
              style={style}
            >
              {children}
            </div>,
            document.body,
          )
        : null}
    </span>
  )
}
