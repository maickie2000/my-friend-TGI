from modules.flow2d.flow2d_xseci import parse_xseci

def bar(done, total):
    if total:
        print(f"{done/total:6.2%}", end="\r")

data = parse_xseci(r"C:\TGI\Test.XSECI", progress_cb=bar)
#data = parse_xseci(r"D:\MILAGROS\TGI\Test.XSECI", progress_cb=bar)

# Listar tiempos
print(list(data.keys())[:3])

# Tomar un tiempo y ver sus secciones
#t0 = next(iter(data))
t0='0001d 08h 00m 00s'
print(t0) 
print(list(data[t0].keys())[:5])

# Acceder a un DataFrame
sec_id= 'XSEC_3'
# sec_id = next(iter(data[t0]))
print(sec_id)
df = data[t0][sec_id]["df"]
print(df)
#print(df.head())
print("Q =", data[t0][sec_id]["Q"], data[t0][sec_id]["Q_units"])
print("Units:", data[t0][sec_id]["units"])





