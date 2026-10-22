// Entrada de máscara (Onda 6): formata dinamicamente. # = dígito, A = letra, demais = literal.
export function applyMask(input: string, mask: string): string {
  let out = "", i = 0;
  for (const m of mask) {
    if (i >= input.length) break;
    if (m === "#") { while (i < input.length && !/\d/.test(input[i])) i++; if (i < input.length) out += input[i++]; }
    else if (m === "A") { while (i < input.length && !/[a-zA-Z]/.test(input[i])) i++; if (i < input.length) out += input[i++]; }
    else { out += m; if (input[i] === m) i++; }
  }
  return out;
}

export const MASKS = { cpf: "###.###.###-##", cnpj: "##.###.###/####-##", phone: "(##) #####-####", cep: "#####-###", date: "##/##/####" };

export function MaskedInput({ mask, value, onChange, placeholder }: {
  mask: string; value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <input value={value} placeholder={placeholder || mask.replace(/#/g, "0").replace(/A/g, "X")}
      onChange={(e) => onChange(applyMask(e.target.value, mask))} inputMode="numeric"
      className="w-full bg-edge border border-edge rounded px-2 py-1.5 text-sm text-text font-mono focus:outline-none focus:border-accent" />
  );
}
