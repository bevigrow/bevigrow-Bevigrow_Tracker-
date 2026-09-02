/**
 * Reusable pagination component for rendering large lists with Show More/Show Less.
 *
 * Usage:
 * ```tsx
 * <PaginatedList items={items} initialCount={10} increment={10}>
 *   {(visibleItems) => (
 *     <div className="space-y-3">
 *       {visibleItems.map(item => <Item key={item.id} {...item} />)}
 *     </div>
 *   )}
 * </PaginatedList>
 * ```
 */
import { useState } from 'react'

interface PaginatedListProps<T> {
  /** Array of items to paginate */
  items: T[]
  /** Initial number of items to display */
  initialCount: number
  /** Number of items to load per "Show More" click */
  increment: number
  /** Render function that receives visible items */
  children: (visibleItems: T[]) => React.ReactNode
  /** Optional: custom styling for container */
  containerClassName?: string
  /** Optional: custom styling for button container */
  buttonContainerClassName?: string
}

export function PaginatedList<T>({
  items,
  initialCount,
  increment,
  children,
  containerClassName = 'space-y-4',
  buttonContainerClassName = 'flex justify-center pt-4',
}: PaginatedListProps<T>) {
  const [visibleCount, setVisibleCount] = useState(initialCount)
  const visibleItems = items.slice(0, visibleCount)
  const hasMore = visibleCount < items.length
  const remaining = items.length - visibleCount

  const handleShowMore = () => {
    setVisibleCount((count) => count + increment)
  }

  const handleShowLess = () => {
    setVisibleCount(initialCount)
  }

  return (
    <div className={containerClassName}>
      {children(visibleItems)}

      {/* Pagination controls */}
      {hasMore && (
        <div className={buttonContainerClassName}>
          <button
            onClick={handleShowMore}
            className="rounded-lg border border-gold/30 bg-gold/5 px-6 py-2.5 font-medium text-gold transition hover:bg-gold/10"
          >
            Show {Math.min(increment, remaining)} more
          </button>
        </div>
      )}

      {visibleCount > initialCount && items.length > initialCount && (
        <div className="flex justify-center pt-2">
          <button
            onClick={handleShowLess}
            className="rounded-lg px-6 py-2.5 font-medium text-latte/60 transition hover:text-latte"
          >
            Show less
          </button>
        </div>
      )}
    </div>
  )
}
