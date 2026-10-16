function Div(el)
  if el.classes:includes("cell-output-stdout")
     or el.classes:includes("cell-output-stderr") then
    return {}
  end
end