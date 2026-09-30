function getPaperUrl(source) {

  // 1. Prefer the best access URL selected by the Research Agent
  if (source.best_access_url) {
    return source.best_access_url;
  }

  // 2. Direct PDF
  if (source.pdf_url) {
    return source.pdf_url;
  }

  // 3. Open-access page
  if (source.oa_url) {
    return source.oa_url;
  }

  // 4. Complete DOI URL returned by backend
  if (source.doi_url) {
    return source.doi_url;
  }

  // 5. Other complete URL
  if (source.url) {
    return source.url;
  }

  // 6. Convert a raw DOI into a real external URL
  if (source.doi) {
    const cleanDoi = source.doi
      .replace(/^https?:\/\/(dx\.)?doi\.org\//i, '')
      .replace(/^doi:\s*/i, '')
      .trim();

    return `https://doi.org/${cleanDoi}`;
  }

  return null;
}

export default function ResearchSources({ sources }) {

  if (!sources?.length) {
    return null;
  }

  return (
    <details className="evidence-drawer">

      <summary>Sources</summary>

      {sources.map((source, index) => {

        const paperUrl = getPaperUrl(source);

        return (
          <div
            className="source"
            key={`${source.title}-${index}`}
          >

            <b>{source.title}</b> ({source.year || 'n.d.'})

            {/* Relevance information */}
            {source.relevance_score !== undefined && (
              <>
                <br />
                <small>
                  Relevance Score: <b>{source.relevance_score}/100</b>
                  {' '}•{' '}
                  Relevance: <b>{source.relevance_level || 'N/A'}</b>
                </small>
              </>
            )}

            {/* Ranking information */}
            {source.rank !== undefined && (
              <>
                <small>
                  {' '}•{' '}
                  Rank: <b>#{source.rank}</b>
                </small>
              </>
            )}

            <br />

            {paperUrl ? (
              <a
                href={paperUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                Open paper ↗
              </a>
            ) : (
              <span>No DOI/URL returned</span>
            )}

            {source.doi && (
              <>
                <br />
                <small>DOI: {source.doi}</small>
              </>
            )}

          </div>
        );
      })}

    </details>
  );
}