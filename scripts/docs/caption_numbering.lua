local figure_counter = 0
local table_counter = 0

local function build_prefix(label, n)
  return pandoc.Inlines({
    pandoc.Str(label),
    pandoc.Space(),
    pandoc.Str(tostring(n) .. "."),
    pandoc.Space(),
  })
end

local function ensure_caption_long(caption, prefix)
  if caption == nil then
    return nil
  end

  local long_blocks = caption.long or {}
  if #long_blocks == 0 then
    caption.long = { pandoc.Plain(prefix) }
    return caption
  end

  local first_block = long_blocks[1]
  if first_block.t == "Plain" or first_block.t == "Para" then
    local merged = pandoc.Inlines({})
    merged:extend(prefix)
    merged:extend(first_block.content)
    first_block.content = merged
    long_blocks[1] = first_block
  else
    table.insert(long_blocks, 1, pandoc.Plain(prefix))
  end
  caption.long = long_blocks
  return caption
end

function Figure(el)
  figure_counter = figure_counter + 1
  local prefix = build_prefix("Hình", figure_counter)
  local caption = ensure_caption_long(el.caption, prefix)
  if caption ~= nil then
    el.caption = caption
  end
  return el
end

function Table(el)
  table_counter = table_counter + 1
  local prefix = build_prefix("Bảng", table_counter)
  local caption = ensure_caption_long(el.caption, prefix)
  if caption ~= nil then
    el.caption = caption
  end
  return el
end
