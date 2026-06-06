// Mavi başlık şeritli kart (trexCloud tarzı).
export default function Card({ title, action, children, noPad }) {
  return (
    <div className="tcard">
      {title && (
        <div className="tcard-head">
          <span>{title}</span>
          {action}
        </div>
      )}
      <div className="tcard-body" style={noPad ? { padding: 0 } : undefined}>{children}</div>
    </div>
  )
}
