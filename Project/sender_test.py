from rdt import RDT

rdt = RDT("127.0.0.1", 5001)
print("Sender ready...")
rdt.send_file_reliable("sample.txt", ("127.0.0.1", 5000))
rdt.close()