import { MatPaginatorIntl } from "@angular/material/paginator";

/**
 * Polish translation for Angular Material's paginator labels.
 * Provided where MatPaginator is used (see ProjectsComponent).
 */
export function polishPaginatorIntl(): MatPaginatorIntl {
  const intl = new MatPaginatorIntl();
  intl.itemsPerPageLabel = "Elementów na stronę:";
  intl.nextPageLabel = "Następna strona";
  intl.previousPageLabel = "Poprzednia strona";
  intl.firstPageLabel = "Pierwsza strona";
  intl.lastPageLabel = "Ostatnia strona";
  intl.getRangeLabel = (page: number, pageSize: number, length: number) => {
    if (length === 0 || pageSize === 0) {
      return `0 z ${length}`;
    }
    const safeLength = Math.max(length, 0);
    const startIndex = page * pageSize;
    const endIndex =
      startIndex < safeLength
        ? Math.min(startIndex + pageSize, safeLength)
        : startIndex + pageSize;
    return `${startIndex + 1} – ${endIndex} z ${safeLength}`;
  };
  return intl;
}
